"""Snapshot folders before touching them (saves, profiles, config, the game's data folder).

    um backup create "C:\\Users\\me\\Documents\\My Games\\Terraria" --name terraria-saves
    um backup list [name]
    um backup diff terraria-saves "C:\\Users\\me\\Documents\\My Games\\Terraria"
    um backup restore terraria-saves [--to DIR] [--snapshot FILE] [--yes]

Snapshots are ZIP files with an integrity manifest in ~/.universal-modder/backups/<name>/.
New snapshots record SHA-1 for backward compatibility and SHA-256 for stronger verification. Restore validates
the complete archive before touching the destination, snapshots the current state, constructs a complete sibling
staging tree, then publishes it with a rollback rename. Static symlink/path checks are fail-closed; callers should
still avoid concurrent mutation of source or destination trees during backup and restore.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

from um.common import data_dir, die, to_posix

MAX_SNAPSHOT_BYTES = 20 << 30
MAX_SNAPSHOT_FILES = 250_000
MAX_MANIFEST_BYTES = 16 << 20
MANIFEST = "_um_manifest.json"


def _safe_name(name: str) -> str:
    if (not isinstance(name, str) or not name or name in {".", ".."} or "/" in name or "\\" in name
            or ":" in name or any(ord(c) < 32 for c in name)):
        die(f"unsafe backup name: {name!r}")
    return name


def _root(name: str) -> Path:
    name = _safe_name(name)
    base = (data_dir() / "backups").resolve()
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    if d.resolve() != base / name:
        die(f"backup path escaped its root: {name!r}")
    return d


def _safe_rel(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or any(ord(c) < 32 for c in value):
        die(f"unsafe snapshot path: {value!r}")
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in {"", ".", ".."} for part in p.parts) or ":" in p.parts[0]:
        die(f"unsafe snapshot path: {value!r}")
    normalized = p.as_posix()
    if normalized != value or normalized == MANIFEST:
        die(f"unsafe snapshot path: {value!r}")
    return normalized


def _source_files(src: Path) -> list[tuple[str, Path]]:
    if src.is_symlink():
        die(f"snapshot source cannot be a symlink: {src}")
    files: list[tuple[str, Path]] = []
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src).as_posix()
        if p.is_symlink():
            die(f"snapshot source contains a symlink: {rel}")
        try:
            mode = p.stat(follow_symlinks=False).st_mode
        except OSError as exc:
            die(f"cannot inspect {p}: {exc}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            die(f"snapshot source contains a non-regular file: {rel}")
        files.append((_safe_rel(rel), p))
        if len(files) > MAX_SNAPSHOT_FILES:
            die(f"snapshot has more than {MAX_SNAPSHOT_FILES:,} files")
    return files


def _digest_stream(stream) -> tuple[int, str, str]:
    size = 0
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    while True:
        chunk = stream.read(1 << 20)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_SNAPSHOT_BYTES:
            die("snapshot data exceeds the 20 GiB safety limit")
        sha1.update(chunk)
        sha256.update(chunk)
    return size, sha1.hexdigest(), sha256.hexdigest()


def _scan(src: Path) -> dict:
    files = {}
    total = 0
    for rel, p in _source_files(src):
        with open(p, "rb") as fh:
            size, sha1, sha256 = _digest_stream(fh)
        total += size
        if total > MAX_SNAPSHOT_BYTES:
            die(f"{total / 2**30:.1f} GB - too big to snapshot casually; back up the specific subfolder you'll change")
        files[rel] = {"size": size, "sha1": sha1, "sha256": sha256}
    return files


def create(src: str, name: str | None = None, note: str = "") -> Path:
    s = Path(to_posix(src)).expanduser()
    if not s.is_dir() or s.is_symlink():
        die(f"not a regular folder: {s}")
    name = _safe_name(name or s.name.replace(" ", "-").lower())
    source_files = _source_files(s)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = _root(name)
    sequences = (p.stem[len(stamp) + 1:] for p in root.glob(f"{stamp}_*.zip"))
    sequence = max((int(n) + 1 for n in sequences if n.isdecimal()), default=0)
    while True:
        suffix = f"_{sequence:06d}" if sequence else ""
        out = root / f"{stamp}{suffix}.zip"
        try:
            z = zipfile.ZipFile(out, "x", zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False)
            break
        except FileExistsError:
            sequence += 1
    files: dict[str, dict] = {}
    total = 0
    try:
        with z:
            for rel, path in source_files:
                z.write(path, rel)
                with z.open(rel) as archived:
                    size, sha1, sha256 = _digest_stream(archived)
                total += size
                if total > MAX_SNAPSHOT_BYTES:
                    die(f"{total / 2**30:.1f} GB - too big to snapshot casually; back up the specific subfolder you'll change")
                files[rel] = {"size": size, "sha1": sha1, "sha256": sha256}
            manifest = json.dumps({"format": 2, "source": str(src), "created": stamp, "note": note, "files": files}, indent=1)
            z.writestr(MANIFEST, manifest)
    except BaseException:
        out.unlink(missing_ok=True)
        raise
    print(f"{out}  ({len(files)} files, {total / 2**20:.1f} MB)")
    return out


def snapshots(name: str) -> list[Path]:
    return sorted(_root(name).glob("*.zip"))


def _regular_zip_member(info: zipfile.ZipInfo) -> bool:
    unix_mode = info.external_attr >> 16
    kind = stat.S_IFMT(unix_mode)
    return kind in (0, stat.S_IFREG)


def _validate_open_zip(z: zipfile.ZipFile, label: Path) -> dict:
    infos = z.infolist()
    names = [i.filename for i in infos]
    if len(names) != len(set(names)):
        die(f"snapshot has duplicate ZIP entries: {label}")
    if MANIFEST not in names:
        die(f"snapshot has no {MANIFEST}: {label}")
    manifest_info = z.getinfo(MANIFEST)
    if manifest_info.file_size > MAX_MANIFEST_BYTES:
        die(f"snapshot manifest is too large: {manifest_info.file_size:,} bytes")
    try:
        manifest = json.loads(z.read(MANIFEST))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        die(f"snapshot manifest is invalid JSON: {exc}")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        die("snapshot manifest must contain a files object")
    files = manifest["files"]
    if len(files) > MAX_SNAPSHOT_FILES:
        die(f"snapshot has more than {MAX_SNAPSHOT_FILES:,} files")
    expected = {MANIFEST}
    total = 0
    for raw_rel, record in files.items():
        rel = _safe_rel(raw_rel)
        expected.add(rel)
        if not isinstance(record, dict) or type(record.get("size")) is not int or record["size"] < 0:
            die(f"snapshot manifest has invalid metadata for {rel}")
        if not re_fullmatch_hex(record.get("sha1"), 40):
            die(f"snapshot manifest has invalid SHA-1 for {rel}")
        if "sha256" in record and not re_fullmatch_hex(record.get("sha256"), 64):
            die(f"snapshot manifest has invalid SHA-256 for {rel}")
        try:
            info = z.getinfo(rel)
        except KeyError:
            die(f"snapshot is missing {rel}")
        if not _regular_zip_member(info):
            die(f"snapshot member is not a regular file: {rel}")
        if info.file_size != record["size"]:
            die(f"snapshot size mismatch for {rel}")
        total += info.file_size
        if total > MAX_SNAPSHOT_BYTES:
            die("snapshot data exceeds the 20 GiB safety limit")
        with z.open(info) as fh:
            size, sha1, sha256 = _digest_stream(fh)
        if size != record["size"] or sha1 != record["sha1"].lower():
            die(f"snapshot integrity check failed for {rel}")
        if record.get("sha256") and sha256 != record["sha256"].lower():
            die(f"snapshot SHA-256 check failed for {rel}")
    if set(names) != expected:
        extras = sorted(set(names) - expected)
        die(f"snapshot has undeclared entries: {', '.join(extras[:5])}")
    return manifest


def _validated_manifest(zp: Path) -> dict:
    try:
        with open(zp, "rb") as raw, zipfile.ZipFile(raw) as z:
            return _validate_open_zip(z, zp)
    except (OSError, zipfile.BadZipFile) as exc:
        die(f"cannot read snapshot {zp}: {exc}")


def re_fullmatch_hex(value, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(c in "0123456789abcdefABCDEF" for c in value)


def _manifest(zp: Path) -> dict:
    return _validated_manifest(zp)


def _diff_manifest(m: dict, target: Path, snapshot: Path) -> dict:
    now = _scan(target) if target.is_dir() else {}
    old = m["files"]
    return {
        "snapshot": str(snapshot),
        "target": str(target),
        "added": sorted(set(now) - set(old)),
        "removed": sorted(set(old) - set(now)),
        "changed": sorted(k for k in set(now) & set(old) if now[k]["sha1"] != old[k]["sha1"]),
    }


def diff(name: str, target: str | None = None, snapshot: str | None = None) -> dict:
    zp = Path(snapshot) if snapshot else (snapshots(name) or [None])[-1]
    if not zp:
        die(f"no snapshots for {name}")
    m = _validated_manifest(zp)
    t = Path(to_posix(target or m["source"]))
    return _diff_manifest(m, t, zp)


def _fsync_dir(path: Path) -> None:
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _swap_receipt(target: Path) -> Path:
    return target.with_name(f".{target.name}.um-swap.json")


def _write_swap_receipt(target: Path, stage: Path, rollback: Path, state: str) -> None:
    receipt = _swap_receipt(target)
    tmp = receipt.with_name(f".{receipt.name}.tmp-{os.getpid()}")
    payload = json.dumps({"format": 1, "stage": stage.name, "rollback": rollback.name, "state": state}).encode()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, receipt)
    _fsync_dir(target.parent)


def _recover_swap(target: Path) -> None:
    receipt = _swap_receipt(target)
    if not receipt.exists() and not receipt.is_symlink():
        return
    if receipt.is_symlink() or not receipt.is_file():
        die(f"unsafe restore transaction receipt: {receipt}")
    try:
        record = json.loads(receipt.read_text(encoding="utf-8"))
        stage = target.parent / record["stage"]
        rollback = target.parent / record["rollback"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        die(f"invalid restore transaction receipt {receipt}: {exc}")
    if (stage.parent != target.parent or rollback.parent != target.parent
            or not stage.name.startswith(f".{target.name}.um-restore-")
            or not rollback.name.startswith(f".{target.name}.um-rollback-")):
        die(f"unsafe restore transaction paths in {receipt}")
    # Topology is authoritative if termination occurred between a rename and
    # its receipt update.
    if not target.exists() and rollback.exists():
        os.replace(rollback, target)
        _fsync_dir(target.parent)
    elif target.exists() and rollback.exists():
        shutil.rmtree(rollback)
        _fsync_dir(target.parent)
    if stage.exists():
        shutil.rmtree(stage)
    receipt.unlink(missing_ok=True)
    _fsync_dir(target.parent)


def _publish_stage(stage: Path, target: Path) -> None:
    rollback = target.with_name(f".{target.name}.um-rollback-{os.getpid()}-{time.time_ns()}")
    moved_old = False
    _write_swap_receipt(target, stage, rollback, "prepared")
    try:
        if target.exists():
            os.replace(target, rollback)
            _fsync_dir(target.parent)
            moved_old = True
            _write_swap_receipt(target, stage, rollback, "old_moved")
        os.replace(stage, target)
        _fsync_dir(target.parent)
        _write_swap_receipt(target, stage, rollback, "published")
    except BaseException:
        if moved_old and rollback.exists() and not target.exists():
            os.replace(rollback, target)
            _fsync_dir(target.parent)
        raise
    if rollback.exists():
        shutil.rmtree(rollback)
        _fsync_dir(target.parent)
    _swap_receipt(target).unlink(missing_ok=True)
    _fsync_dir(target.parent)


def restore(name: str, to: str | None = None, snapshot: str | None = None, clean: bool = False, yes: bool = False):
    name = _safe_name(name)
    zp = Path(snapshot) if snapshot else (snapshots(name) or [None])[-1]
    if not zp:
        die(f"no snapshots for {name}")
    try:
        # Bind validation and extraction to one open descriptor. Replacing the
        # snapshot pathname after validation cannot change the consumed bytes.
        with open(zp, "rb") as raw, zipfile.ZipFile(raw) as z:
            m = _validate_open_zip(z, zp)
            t = Path(to_posix(to or m["source"])).expanduser()
            t.parent.mkdir(parents=True, exist_ok=True)
            _recover_swap(t)
            if t.is_symlink():
                die(f"restore target cannot be a symlink: {t}")
            d = _diff_manifest(m, t, zp)
            print(f"restore {zp.name} -> {t}: {len(d['changed'])} changed, {len(d['removed'])} missing, {len(d['added'])} new since"
                  + (" (new files will be deleted: --clean)" if clean else " (new files kept)"))
            if not yes:
                die("re-run with --yes to do it")
            if t.is_dir():
                create(str(t), name + "-pre-restore", note=f"automatic, before restoring {zp.name}")
            elif t.exists():
                die(f"restore target is not a folder: {t}")
            t.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix=f".{t.name}.um-restore-", dir=t.parent))
            try:
                if t.is_dir() and not clean:
                    _source_files(t)
                    shutil.copytree(t, stage, dirs_exist_ok=True, symlinks=False)
                for rel, record in m["files"].items():
                    safe_rel = _safe_rel(rel)
                    dst = stage.joinpath(*PurePosixPath(safe_rel).parts)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dst.with_name(f".{dst.name}.um-part-{os.getpid()}")
                    with z.open(safe_rel) as src, open(tmp, "xb") as out:
                        size = 0
                        sha1 = hashlib.sha1()
                        sha256 = hashlib.sha256()
                        for chunk in iter(lambda: src.read(1 << 20), b""):
                            size += len(chunk)
                            if size > record["size"]:
                                die(f"snapshot changed during extraction: {safe_rel}")
                            sha1.update(chunk)
                            sha256.update(chunk)
                            out.write(chunk)
                        out.flush()
                        os.fsync(out.fileno())
                    if (size != record["size"] or sha1.hexdigest() != record["sha1"].lower()
                            or (record.get("sha256") and sha256.hexdigest() != record["sha256"].lower())):
                        tmp.unlink(missing_ok=True)
                        die(f"snapshot changed during extraction: {safe_rel}")
                    os.replace(tmp, dst)
                _publish_stage(stage, t)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
    except (OSError, zipfile.BadZipFile) as exc:
        die(f"cannot restore snapshot {zp}: {exc}")
    print("restored", len(m["files"]), "files")


def main(a):
    if a.cmd == "create":
        create(a.src, a.name, a.note or "")
    elif a.cmd == "list":
        root = data_dir() / "backups"
        names = [a.name] if a.name else sorted(p.name for p in root.glob("*") if p.is_dir()) if root.exists() else []
        for n in names:
            for zp in snapshots(n):
                m = _manifest(zp)
                print(f"{n:28} {zp.name}  {len(m['files']):5} files  {m['source']}  {m.get('note', '')}")
    elif a.cmd == "diff":
        print(json.dumps(diff(a.name, a.target, a.snapshot), indent=1))
    elif a.cmd == "restore":
        restore(a.name, a.to, a.snapshot, a.clean, a.yes)


def register(sub):
    import argparse
    p = sub.add_parser("backup", help="snapshot / diff / restore save folders before you touch them",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")
    q = cs.add_parser("create", help="snapshot a folder")
    q.add_argument("src")
    q.add_argument("--name")
    q.add_argument("--note")
    q.set_defaults(func=main)
    q = cs.add_parser("list", help="list snapshots")
    q.add_argument("name", nargs="?")
    q.set_defaults(func=main)
    q = cs.add_parser("diff", help="what changed since the latest snapshot")
    q.add_argument("name")
    q.add_argument("target", nargs="?")
    q.add_argument("--snapshot")
    q.set_defaults(func=main)
    q = cs.add_parser("restore", help="restore the latest (or --snapshot) snapshot")
    q.add_argument("name")
    q.add_argument("--to")
    q.add_argument("--snapshot")
    q.add_argument("--clean", action="store_true", help="also delete files created after the snapshot")
    q.add_argument("--yes", action="store_true")
    q.set_defaults(func=main)
