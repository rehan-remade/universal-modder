"""Snapshot folders before touching them (saves, profiles, config, the game's data folder).

    um backup create "C:\\Users\\me\\Documents\\My Games\\Terraria" --name terraria-saves
    um backup list [name]
    um backup diff terraria-saves "C:\\Users\\me\\Documents\\My Games\\Terraria"     # what changed since the last snapshot
    um backup restore terraria-saves [--to DIR] [--snapshot FILE] [--yes]

Snapshots are zip files + a manifest (size + sha1 per file) in ~/.universal-modder/backups/<name>/.
Snapshots created in the same second get numbered suffixes so earlier backups are never overwritten.
restore first snapshots the current state (so a restore can itself be undone), then puts every file
back and removes files that weren't in the snapshot only with --clean.
Habit that saved the Terraria showcase: keep a pristine copy of any world/scenario a scripted take
destroys, and restore it before each take.
"""
from __future__ import annotations

import hashlib
import json
import time
import zipfile
from pathlib import Path

from um.common import data_dir, die, to_posix


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
    s = Path(to_posix(src)).expanduser()
    if not s.is_dir():
        die(f"not a folder: {s}")
    name = name or s.name.replace(" ", "-").lower()
    files = _scan(s)
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
            z.writestr("_um_manifest.json", json.dumps(dict(source=str(src), created=stamp, note=note, files=files), indent=1))
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


def diff(name: str, target: str | None = None, snapshot: str | None = None) -> dict:
    zp = Path(snapshot) if snapshot else (snapshots(name) or [None])[-1]
    if not zp:
        die(f"no snapshots for {name}")
    m = _manifest(zp)
    t = Path(to_posix(target or m["source"]))
    now = _scan(t) if t.is_dir() else {}
    old = m["files"]
    res = dict(snapshot=str(zp), target=str(t),
               added=sorted(set(now) - set(old)), removed=sorted(set(old) - set(now)),
               changed=sorted(k for k in set(now) & set(old) if now[k]["sha1"] != old[k]["sha1"]))
    return res


def restore(name: str, to: str | None = None, snapshot: str | None = None, clean: bool = False, yes: bool = False):
    zp = Path(snapshot) if snapshot else (snapshots(name) or [None])[-1]
    if not zp:
        die(f"no snapshots for {name}")
    m = _manifest(zp)
    t = Path(to_posix(to or m["source"]))
    d = diff(name, str(t), str(zp))
    print(f"restore {zp.name} -> {t}: {len(d['changed'])} changed, {len(d['removed'])} missing, {len(d['added'])} new since"
          + (" (new files will be deleted: --clean)" if clean else " (new files kept)"))
    if not yes:
        die("re-run with --yes to do it")
    if t.is_dir():
        create(str(t), name + "-pre-restore", note=f"automatic, before restoring {zp.name}")
    t.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zp) as z:
        for rel in m["files"]:
            (t / rel).parent.mkdir(parents=True, exist_ok=True)
            with z.open(rel) as src, open(t / rel, "wb") as dst:
                dst.write(src.read())
    if clean:
        for rel in d["added"]:
            (t / rel).unlink(missing_ok=True)
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
