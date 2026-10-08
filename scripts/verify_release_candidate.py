#!/usr/bin/env python3
"""Verify two reproducible distributions against the exact source checkout."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

PROJECT = "universal-modder"
DIST = "universal_modder"
VERSION = "0.2.0"
MAX_ARCHIVE_BYTES = 512 << 20
MAX_EXPANDED_BYTES = 2 << 30
MAX_MEMBERS = 100_000
FORBIDDEN_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".idea", ".vs"}
SENSITIVE_NAMES = {".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials.json"}


def safe_name(name: str) -> bool:
    if not name or "\\" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        return False
    if re.match(r"^[A-Za-z]:", name):
        return False
    path = PurePosixPath(name)
    parts = path.parts
    return (not path.is_absolute() and all(part not in {"", ".", ".."} for part in parts)
            and path.as_posix() == name.rstrip("/"))


def validate_names(names: list[str], label: Path) -> None:
    normalized = [name.rstrip("/") for name in names]
    if len(names) > MAX_MEMBERS or len(normalized) != len(set(normalized)):
        raise SystemExit(f"too many or duplicate archive members in {label}")
    folded: dict[str, str] = {}
    files = set(normalized)
    for name in normalized:
        if not safe_name(name):
            raise SystemExit(f"unsafe archive member {name!r} in {label}")
        prior = folded.setdefault(name.casefold(), name)
        if prior != name:
            raise SystemExit(f"case-fold collision in {label}: {prior!r} and {name!r}")
        parts = PurePosixPath(name).parts
        for i in range(1, len(parts)):
            if "/".join(parts[:i]) in files:
                raise SystemExit(f"file/directory prefix collision in {label}: {name!r}")


def validate_record_rows(rows: list[list[str]], expected_names: set[str]) -> None:
    if any(len(row) != 3 for row in rows):
        raise SystemExit("wheel RECORD contains a malformed row")
    recorded = [row[0] for row in rows]
    if len(recorded) != len(set(recorded)) or set(recorded) != expected_names:
        raise SystemExit("wheel RECORD inventory mismatch")


def validate_sdist_paths(names: list[str]) -> None:
    for name in names:
        parts = PurePosixPath(name.rstrip("/")).parts
        if FORBIDDEN_PARTS.intersection(parts) or (parts and parts[-1].lower() in SENSITIVE_NAMES):
            raise SystemExit(f"forbidden path in sdist: {name}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def source_binding(source: Path) -> dict[str, object]:
    try:
        before = os.stat(source, follow_symlinks=False)
    except OSError as exc:
        raise SystemExit(f"cannot bind distribution input {source}: {exc}") from exc
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_ARCHIVE_BYTES:
        raise SystemExit(f"distribution input is not a unique acceptable regular file: {source}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(source, flags)
    except OSError as exc:
        raise SystemExit(f"cannot open distribution input {source}: {exc}") from exc
    try:
        opened = os.fstat(fd)
        if opened.st_nlink != 1 or _file_identity(opened) != _file_identity(before):
            raise SystemExit(f"distribution input changed before binding: {source}")
        value = hashlib.sha256()
        for chunk in iter(lambda: os.read(fd, 1 << 20), b""):
            value.update(chunk)
        after = os.fstat(fd)
        try:
            path_after = os.stat(source, follow_symlinks=False)
        except OSError as exc:
            raise SystemExit(f"distribution input changed while binding {source}: {exc}") from exc
        if (_file_identity(after) != _file_identity(opened)
                or _file_identity(path_after) != _file_identity(opened)):
            raise SystemExit(f"distribution input changed while binding: {source}")
        return {"identity": _file_identity(opened), "sha256": value.hexdigest()}
    finally:
        os.close(fd)


def verify_source_binding(source: Path, binding: dict[str, object]) -> None:
    current = source_binding(source)
    if current != binding:
        raise SystemExit(f"distribution input changed after snapshot: {source}")


def _git_output(command: list[str], root: Path, *, text: bool = False):
    env = dict(os.environ)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    return subprocess.check_output(command, cwd=root, text=text, env=env)


def snapshot_regular_file(source: Path, destination: Path) -> Path:
    """Snapshot one stable regular file through a validated descriptor."""
    try:
        before = os.stat(source, follow_symlinks=False)
    except OSError as exc:
        raise SystemExit(f"cannot inspect distribution input {source}: {exc}") from exc
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_ARCHIVE_BYTES:
        raise SystemExit(f"distribution input is not an acceptable regular file: {source}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        source_fd = os.open(source, flags)
    except OSError as exc:
        raise SystemExit(f"cannot open distribution input safely {source}: {exc}") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    output_fd: int | None = None
    destination_created = False
    try:
        opened = os.fstat(source_fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or _file_identity(opened) != _file_identity(before):
            raise SystemExit(f"distribution input changed before descriptor binding: {source}")
        output_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0), 0o600)
        destination_created = True
        while True:
            chunk = os.read(source_fd, 1 << 20)
            if not chunk:
                break
            view = memoryview(chunk)
            while view:
                written = os.write(output_fd, view)
                if written <= 0:
                    raise SystemExit(f"could not snapshot distribution input: {source}")
                view = view[written:]
        os.fsync(output_fd)
        after = os.fstat(source_fd)
        try:
            path_after = os.stat(source, follow_symlinks=False)
        except OSError as exc:
            raise SystemExit(f"distribution input disappeared during verification: {source}") from exc
        if _file_identity(after) != _file_identity(opened) or _file_identity(path_after) != _file_identity(opened):
            raise SystemExit(f"distribution input changed during verification: {source}")
    except BaseException:
        if destination_created:
            destination.unlink(missing_ok=True)
        raise
    finally:
        if output_fd is not None:
            os.close(output_fd)
        os.close(source_fd)
    return destination


def source_identity(root: Path) -> dict[str, str]:
    status = _git_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], root, text=True)
    if status:
        raise SystemExit("source checkout is dirty; release artifacts must bind to clean committed bytes")
    commit = _git_output(["git", "rev-parse", "HEAD"], root, text=True).strip()
    tree = _git_output(["git", "rev-parse", f"{commit}^{{tree}}"], root, text=True).strip()
    return {"commit": commit, "tree": tree}


def git_paths(root: Path, commit: str, prefix: str | None = None) -> set[str]:
    command = ["git", "ls-tree", "-r", "--name-only", "-z", commit]
    if prefix is not None:
        command += ["--", prefix]
    payload = _git_output(command, root).decode()
    return {name for name in payload.rstrip("\0").split("\0") if name}


def git_blob(root: Path, commit: str, rel: str) -> bytes:
    return _git_output(["git", "show", f"{commit}:{rel}"], root)


def metadata_identity(payload: bytes, label: str) -> None:
    meta = BytesParser().parsebytes(payload)
    if meta.get("Name") != PROJECT or meta.get("Version") != VERSION:
        raise SystemExit(f"wrong distribution identity in {label}: {meta.get('Name')} {meta.get('Version')}")


def inspect_wheel(path: Path, root: Path, commit: str) -> list[str]:
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise SystemExit(f"wheel is too large: {path}")
    dist_info = f"{DIST}-{VERSION}.dist-info"
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        validate_names(names, path)
        if sum(i.file_size for i in infos) > MAX_EXPANDED_BYTES:
            raise SystemExit(f"wheel expands beyond limit: {path}")
        for info in infos:
            kind = stat.S_IFMT(info.external_attr >> 16)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise SystemExit(f"non-regular wheel member: {info.filename}")
        source_files = git_paths(root, commit, "um")
        metadata_files = {
            f"{dist_info}/METADATA", f"{dist_info}/WHEEL", f"{dist_info}/entry_points.txt",
            f"{dist_info}/licenses/LICENSE", f"{dist_info}/RECORD",
        }
        if set(names) != source_files | metadata_files:
            extra = sorted(set(names) - source_files - metadata_files)
            missing = sorted(source_files | metadata_files - set(names))
            raise SystemExit(f"wheel inventory mismatch; extra={extra[:8]} missing={missing[:8]}")
        for source_name in source_files:
            if archive.read(source_name) != git_blob(root, commit, source_name):
                raise SystemExit(f"wheel bytes differ from source: {source_name}")
        metadata_identity(archive.read(f"{dist_info}/METADATA"), path.name)
        record_name = f"{dist_info}/RECORD"
        rows = list(csv.reader(io.StringIO(archive.read(record_name).decode("utf-8"))))
        validate_record_rows(rows, set(names))
        for name, encoded, size in rows:
            if name == record_name:
                if encoded or size:
                    raise SystemExit("wheel RECORD must not hash itself")
                continue
            payload = archive.read(name)
            expected = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
            if encoded != expected or size != str(len(payload)):
                raise SystemExit(f"wheel RECORD mismatch for {name}")
        return names


def inspect_sdist(path: Path, root: Path, commit: str) -> list[str]:
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise SystemExit(f"sdist is too large: {path}")
    prefix = f"{DIST}-{VERSION}"
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        validate_names(names, path)
        validate_sdist_paths(names)
        if len(members) > MAX_MEMBERS or sum(m.size for m in members if m.isfile()) > MAX_EXPANDED_BYTES:
            raise SystemExit(f"sdist exceeds member or expanded-size limit: {path}")
        if any(not (m.isfile() or m.isdir()) for m in members):
            raise SystemExit(f"non-regular sdist member in {path}")
        files = {m.name: m for m in members if m.isfile()}
        expected_paths = git_paths(root, commit)
        expected = {f"{prefix}/{name}" for name in expected_paths} | {f"{prefix}/PKG-INFO"}
        if set(files) != expected:
            extra = sorted(set(files) - expected)
            missing = sorted(expected - set(files))
            raise SystemExit(f"sdist inventory mismatch; extra={extra[:8]} missing={missing[:8]}")
        expected_dirs = {prefix}
        for name in expected:
            parent = PurePosixPath(name).parent
            while parent.as_posix() != ".":
                expected_dirs.add(parent.as_posix())
                if parent.as_posix() == prefix:
                    break
                parent = parent.parent
        actual_dirs = {m.name.rstrip("/") for m in members if m.isdir()}
        unexpected_dirs = actual_dirs - expected_dirs
        if unexpected_dirs:
            raise SystemExit(f"sdist directory inventory mismatch; extra={sorted(unexpected_dirs)[:8]}")
        for member_name, member in files.items():
            rel = PurePosixPath(member_name).relative_to(prefix)
            extracted = archive.extractfile(member)
            if extracted is None:
                raise SystemExit(f"cannot read sdist member: {member_name}")
            payload = extracted.read()
            if rel.as_posix() == "PKG-INFO":
                metadata_identity(payload, path.name)
            elif payload != git_blob(root, commit, rel.as_posix()):
                raise SystemExit(f"sdist bytes differ from source: {rel}")
        return names


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_release_candidate.py BUILD_A BUILD_B")
    root = Path(__file__).resolve().parents[1]
    left, right = map(Path, sys.argv[1:])
    identity = source_identity(root)
    commit = identity["commit"]

    expected_names = {f"{DIST}-{VERSION}-py3-none-any.whl", f"{DIST}-{VERSION}.tar.gz"}
    with tempfile.TemporaryDirectory(prefix="um-release-verification-") as temporary:
        snapshot_root = Path(temporary)
        bindings: list[tuple[Path, dict[str, object]]] = []

        def distributions(directory: Path, label: str) -> dict[str, Path]:
            try:
                entries = list(directory.iterdir())
            except OSError as exc:
                raise SystemExit(f"cannot enumerate distribution directory {directory}: {exc}") from exc
            if {entry.name for entry in entries} != expected_names or len(entries) != len(expected_names):
                raise SystemExit(f"distribution names must be exactly {sorted(expected_names)}")
            snapshots = {}
            for entry in entries:
                snapshot = snapshot_regular_file(entry, snapshot_root / label / entry.name)
                binding = source_binding(entry)
                if binding["sha256"] != digest(snapshot):
                    raise SystemExit(f"distribution input changed while binding snapshot: {entry}")
                bindings.append((entry, binding))
                snapshots[entry.name] = snapshot
            return snapshots

        a, b = distributions(left, "a"), distributions(right, "b")
        receipt: dict[str, object] = {"source": identity}
        for name in sorted(a):
            if digest(a[name]) != digest(b[name]):
                raise SystemExit(f"non-reproducible distribution bytes: {name}")
            members = inspect_wheel(a[name], root, commit) if name.endswith(".whl") else inspect_sdist(a[name], root, commit)
            receipt[name] = {"sha256": digest(a[name]), "bytes": a[name].stat().st_size, "members": len(members)}
    if source_identity(root) != identity:
        raise SystemExit("source checkout identity changed during release verification")
    for source, binding in bindings:
        verify_source_binding(source, binding)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
