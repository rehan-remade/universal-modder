#!/usr/bin/env python3
"""Verify two reproducible distributions against the exact source checkout."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import stat
import subprocess
import sys
import tarfile
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


def metadata_identity(payload: bytes, label: str) -> None:
    meta = BytesParser().parsebytes(payload)
    if meta.get("Name") != PROJECT or meta.get("Version") != VERSION:
        raise SystemExit(f"wrong distribution identity in {label}: {meta.get('Name')} {meta.get('Version')}")


def inspect_wheel(path: Path, root: Path) -> list[str]:
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
        source_files = {p.relative_to(root).as_posix() for p in (root / "um").rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
        metadata_files = {
            f"{dist_info}/METADATA", f"{dist_info}/WHEEL", f"{dist_info}/entry_points.txt",
            f"{dist_info}/licenses/LICENSE", f"{dist_info}/RECORD",
        }
        if set(names) != source_files | metadata_files:
            extra = sorted(set(names) - source_files - metadata_files)
            missing = sorted(source_files | metadata_files - set(names))
            raise SystemExit(f"wheel inventory mismatch; extra={extra[:8]} missing={missing[:8]}")
        for source_name in source_files:
            if archive.read(source_name) != (root / source_name).read_bytes():
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


def inspect_sdist(path: Path, root: Path) -> list[str]:
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
        expected_paths = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().rstrip("\0").split("\0"))
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
            elif payload != (root / rel).read_bytes():
                raise SystemExit(f"sdist bytes differ from source: {rel}")
        return names


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_release_candidate.py BUILD_A BUILD_B")
    root = Path(__file__).resolve().parents[1]
    left, right = map(Path, sys.argv[1:])

    def distributions(directory: Path) -> dict[str, Path]:
        return {p.name: p for p in directory.iterdir() if p.is_file() and (p.suffix == ".whl" or p.name.endswith(".tar.gz"))}

    expected_names = {f"{DIST}-{VERSION}-py3-none-any.whl", f"{DIST}-{VERSION}.tar.gz"}
    a, b = distributions(left), distributions(right)
    if set(a) != expected_names or set(b) != expected_names:
        raise SystemExit(f"distribution names must be exactly {sorted(expected_names)}")
    receipt = {}
    for name in sorted(a):
        if digest(a[name]) != digest(b[name]):
            raise SystemExit(f"non-reproducible distribution bytes: {name}")
        members = inspect_wheel(a[name], root) if name.endswith(".whl") else inspect_sdist(a[name], root)
        receipt[name] = {"sha256": digest(a[name]), "bytes": a[name].stat().st_size, "members": len(members)}
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
