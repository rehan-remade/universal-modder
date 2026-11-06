"""Snapshot folders before touching them (saves, profiles, config, the game's data folder).

    um backup create "C:\\Users\\me\\Documents\\My Games\\Terraria" --name terraria-saves
    um backup list [name]
    um backup diff terraria-saves "C:\\Users\\me\\Documents\\My Games\\Terraria"     # what changed since the last snapshot
    um backup restore terraria-saves [--to DIR] [--snapshot FILE] [--yes]

Snapshots are zip files + a manifest (size + sha1 per file) in ~/.universal-modder/backups/<name>/.
Snapshots created in the same second get numbered suffixes so earlier backups are never overwritten.
restore without --to (and diff without TARGET) use the folder the snapshot was taken from, recorded as an absolute
path; older snapshots that recorded a relative path need the folder named explicitly.
restore first checks every file: it must stay inside the folder, go through no symlink or junction and
match the manifest's size and sha1, or nothing changes. Then it snapshots the current state (so a
restore can itself be undone), puts every file back and removes files that weren't in the snapshot
only with --clean.
Habit that saved the Terraria showcase: keep a pristine copy of any world/scenario a scripted take
destroys, and restore it before each take.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import zipfile
import zlib
from pathlib import Path

from um.common import data_dir, die, inside, open_out, to_posix


def _root(name: str) -> Path:
    d = data_dir() / "backups" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _scan(src: Path) -> dict:
    files = {}
    for p in sorted(src.rglob("*")):
        if p.is_file():
            h = hashlib.sha1()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            files[p.relative_to(src).as_posix()] = dict(size=p.stat().st_size, sha1=h.hexdigest())
    return files


def create(src: str, name: str | None = None, note: str = "") -> Path:
    # Absolute, so a later restore or diff from another working directory finds the same folder.
    # absolute(), not resolve() or abspath: keep a symlinked save folder's own name and path.
    s = Path(to_posix(src)).expanduser().absolute()
    if not s.is_absolute():  # drive-relative "C:saves" on Windows before Python 3.12
        s = Path(os.path.abspath(s))
    if ".." in s.parts:  # cwd/../saves would need that cwd to still exist; resolve() asks the OS what link/.. means
        s = s.resolve()
    if not s.is_dir():
        die(f"not a folder: {s}")
    name = name or s.name.replace(" ", "-").lower()
    files = _scan(s)
    if "_um_manifest.json" in files:
        die(f"{s} contains reserved snapshot metadata file: _um_manifest.json. Move or rename it, then run this "
            "again (one left over from unzipping a snapshot can simply go)")
    total = sum(f["size"] for f in files.values())
    if total > 20 << 30:
        die(f"{total / 2**30:.1f} GB - too big to snapshot casually; back up the specific subfolder you'll change")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = _root(name)
    # Don't reuse gaps left by deleted or failed backups: a new snapshot must sort after the existing ones.
    sequences = (p.stem[len(stamp) + 1:] for p in root.glob(f"{stamp}_*.zip"))
    sequence = max((int(n) + 1 for n in sequences if n.isdecimal()), default=0)
    while True:
        # '_' sorts after the original .zip; padding keeps the latest snapshot last even after 10+ collisions.
        suffix = f"_{sequence:06d}" if sequence else ""
        out = root / f"{stamp}{suffix}.zip"
        try:
            # Exclusive creation also prevents concurrent backups from overwriting each other.
            # strict_timestamps=False: some folders (e.g. Chromium caches in .minecraft) hold pre-1980 mtimes
            z = zipfile.ZipFile(out, "x", zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False)
            break
        except FileExistsError:
            sequence += 1
    try:
        with z:
            for rel in files:
                z.write(s / rel, rel)
            z.writestr("_um_manifest.json", json.dumps(dict(source=str(s), created=stamp, note=note, files=files), indent=1))
    except BaseException:
        out.unlink(missing_ok=True)  # don't leave an incomplete archive as the latest snapshot
        raise
    print(f"{out}  ({len(files)} files, {total / 2**20:.1f} MB)")
    return out


def snapshots(name: str) -> list[Path]:
    return sorted(_root(name).glob("*.zip"))


def _manifest(zp: Path) -> dict:
    with zipfile.ZipFile(zp) as z:
        return json.loads(z.read("_um_manifest.json"))


def _target(name: str, m: dict, override: str | None) -> Path:
    if override:
        return Path(to_posix(override)).expanduser()
    t = Path(to_posix(m["source"])).expanduser()
    if not t.is_absolute():
        # Snapshots made before sources were stored absolute: the folder depends on the current directory.
        die(f"snapshot records a relative source ({m['source']}); name the folder: "
            f"`um backup restore {name} --to DIR` or `um backup diff {name} DIR`")
    return t


def diff(name: str, target: str | None = None, snapshot: str | None = None) -> dict:
    zp = Path(snapshot) if snapshot else (snapshots(name) or [None])[-1]
    if not zp:
        die(f"no snapshots for {name}")
    m = _manifest(zp)
    t = _target(name, m, target)
    now = _scan(t) if t.is_dir() else {}
    old = m["files"]
    res = dict(snapshot=str(zp), target=str(t),
               added=sorted(set(now) - set(old)), removed=sorted(set(old) - set(now)),
               changed=sorted(k for k in set(now) & set(old) if now[k]["sha1"] != old[k]["sha1"]))
    return res


def _intact(z: zipfile.ZipFile, info: zipfile.ZipInfo, want: dict) -> bool:
    """The member has the size and SHA-1 the manifest recorded for it (each one it recorded)."""
    if "size" in want and info.file_size != want["size"]:
        return False
    if "sha1" not in want:
        return True
    h = hashlib.sha1()
    try:
        with z.open(info) as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except (zipfile.BadZipFile, zlib.error, EOFError):  # a bad CRC, deflate stream or length
        return False
    return h.hexdigest() == want["sha1"]


def _check(zp: Path, z: zipfile.ZipFile, m: dict, root: Path, deletes: list[str]) -> dict:
    """{file: its zip member}, or die before anything changes: every file restore writes or --clean deletes stays in
    root and goes through no symlink or junction, and every member matches the manifest."""
    def refuse(bad: list[str], why: str):
        more = f"\n  ...and {len(bad) - 10} more" if len(bad) > 10 else ""
        die(f"not restoring {zp.name}, nothing was changed:\n  " + "\n  ".join(bad[:10]) + more + "\n" + why)

    bad = []
    for rel in [*m["files"], *deletes]:
        try:
            inside(root, rel)
        except ValueError as e:
            bad.append(f"{rel}: {e}")
    if bad:
        refuse(bad, "restore writes only inside the folder, never through a symlink or junction (if the folder has one, "
                    "remove it or restore --to an empty folder)")
    # older snapshots of a folder with its own _um_manifest.json hold two members of that name: its file, then ours
    first = {info.filename: info for info in reversed(z.infolist())}
    members = {rel: first.get(rel) for rel in m["files"]}
    bad = [f"{rel}: " + ("not in the snapshot" if info is None else "size or SHA-1 differs from the manifest")
           for rel, info in members.items() if info is None or not _intact(z, info, m["files"][rel])]
    if bad:
        refuse(bad, "the snapshot is damaged, or was changed after um made it")
    return members


def restore(name: str, to: str | None = None, snapshot: str | None = None, clean: bool = False, yes: bool = False):
    zp = Path(snapshot) if snapshot else (snapshots(name) or [None])[-1]
    if not zp:
        die(f"no snapshots for {name}")
    m = _manifest(zp)
    t = _target(name, m, to)
    d = diff(name, str(t), str(zp))
    print(f"restore {zp.name} -> {t}: {len(d['changed'])} changed, {len(d['removed'])} missing, {len(d['added'])} new since"
          + (" (new files will be deleted: --clean)" if clean else " (new files kept)"))
    root = t.resolve()  # t may be a link (saves moved to another drive); nothing below it is followed
    with zipfile.ZipFile(zp) as z:
        members = _check(zp, z, m, root, d["added"] if clean else [])
        if not yes:
            die("re-run with --yes to do it")
        if t.is_dir():
            create(str(t), name + "-pre-restore", note=f"automatic, before restoring {zp.name}")
        root.mkdir(parents=True, exist_ok=True)
        for rel, info in members.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open_out(root / rel) as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
    if clean:
        for rel in d["added"]:
            (root / rel).unlink(missing_ok=True)
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
