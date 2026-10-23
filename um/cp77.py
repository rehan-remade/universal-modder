"""Cyberpunk 2077 mod manager: install Nexus files into the game, track every file placed, and see which
.archive overrides what, before anything conflicts.

    um cp77 game [PATH] [--wolvenkit EXE]   # show or set the install folder (auto-detects Steam / GOG)
    um cp77 install 1234 [5678 ...] [--file ID] [--name NAME] [--pick SUBFOLDER] [--replace] [--overwrite] [--dry]
    um cp77 install C:\\dl\\mod.zip         # a downloaded archive, a folder, or an nxm:// link
    um cp77 list                            # installed mods, versions, file counts
    um cp77 files NAME                      # every file a mod placed
    um cp77 uninstall NAME [--force]        # remove exactly the files it placed, restore what it replaced
    um cp77 conflicts [NAME] [--paths]      # archives touching the same paths, and who wins by load order
    um cp77 check                           # changed or missing files, archives nobody recorded
    um cp77 hashes ARCHIVE [--names]        # path hashes (and names via WolvenKit) in a .archive
    um cp77 vanilla-index                   # cache the vanilla archives' hash set so conflicts show overrides
    um cp77 updates                         # which installed Nexus mods have a newer main file
    um cp77 loaders                         # CET, RED4ext, ArchiveXL, TweakXL, redscript, REDmod present?

State lives in ~/.universal-modder/cp77/ (manifest.json, config.json, vanilla-hashes.npy). Mods are copied
from the extracted download into the game folder, never linked, so deleting a download never breaks the
game and uninstalling never touches the download. A Nexus download's sidecar (`um nexus`) is recorded, so
`updates` knows what to compare. Load order in archive/pc/mod: modlist.txt first (in its order), then the
rest in name order, and the archive loaded first wins a path; that is why mods ship as `!!!Name.archive`.
Names come from WolvenKit's CLI when it is installed (`um cp77 game --wolvenkit PATH`); without it,
conflicts are reported by path hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from um.common import data_dir, die, emit, is_windows, text_utf8, to_posix

GAME_DOMAIN = "cyberpunk2077"
MOD_DIR = "archive/pc/mod"
CET_MODS = "bin/x64/plugins/cyber_engine_tweaks/mods"
VANILLA_DIRS = ("archive/pc/content", "archive/pc/ep1")
# top-level folders a mod archive can contain, and what must follow for the match to count
ROOTS: dict[str, tuple[str, ...] | None] = {
    "archive": ("pc",),
    "r6": ("scripts", "tweaks", "config", "input", "cache", "audioware", "storages"),
    "red4ext": ("plugins", "red4ext.dll", "config.ini"),
    "bin": ("x64",),
    "engine": ("config", "tools"),
    "tools": ("redmod", "cybercmd"),
    "mods": None,  # REDmod: only when a */info.json sits under it (checked separately)
}
SKIP_EXT = {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".url", ".html", ".htm", ".rtf", ".docx", ".psd"}
SKIP_NAMES = {"__folder_managed_by_vortex", "placeholder.vortex", "please_vortex_dont_ignore_this_folder", "desktop.ini", "thumbs.db"}
LOADERS = [
    ("Cyber Engine Tweaks", ["bin/x64/plugins/cyber_engine_tweaks.asi", "bin/x64/version.dll"]),
    ("RED4ext", ["red4ext/RED4ext.dll", "bin/x64/winmm.dll"]),
    ("ArchiveXL", ["red4ext/plugins/ArchiveXL/ArchiveXL.dll"]),
    ("TweakXL", ["red4ext/plugins/TweakXL/TweakXL.dll"]),
    ("Codeware", ["red4ext/plugins/Codeware/Codeware.dll"]),
    ("redscript", ["engine/tools/scc.exe"]),
    ("REDmod (official DLC)", ["tools/redmod/bin/redMod.exe"]),
]
FNV_OFFSET, FNV_PRIME = 0xCBF29CE484222325, 0x100000001B3


class Cp77Error(Exception):
    pass


# --------------------------------------------------------------------------- state

def state_dir() -> Path:
    d = data_dir() / "cp77"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load(name: str) -> dict:
    p = state_dir() / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(name: str, obj: dict):
    p = state_dir() / name
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    tmp.replace(p)


def config() -> dict:
    return _load("config.json")


def manifest() -> dict:
    m = _load("manifest.json")
    m.setdefault("mods", {})
    return m


def detect_game() -> Path | None:
    from um import scan
    try:
        for g in scan.steam_games():
            if (g.get("name") or "").lower().startswith("cyberpunk 2077") and _is_game(Path(g["path"])):
                return Path(g["path"])
    except Exception:  # scan is best-effort: any registry or vdf trouble just means "not found"
        pass
    for p in (r"C:\Program Files (x86)\GOG Galaxy\Games\Cyberpunk 2077", r"C:\GOG Games\Cyberpunk 2077",
              r"C:\Program Files\Epic Games\Cyberpunk 2077"):
        if _is_game(Path(to_posix(p))):
            return Path(to_posix(p))
    return None


def _is_game(p: Path) -> bool:
    return (p / "bin" / "x64" / "Cyberpunk2077.exe").is_file()


def game_dir() -> Path:
    c = config()
    if c.get("game"):
        p = Path(to_posix(c["game"]))
        if _is_game(p):
            return p
        raise Cp77Error(f"configured game folder has no bin/x64/Cyberpunk2077.exe: {p}\n`um cp77 game PATH` to fix it")
    p = detect_game()
    if not p:
        raise Cp77Error("Cyberpunk 2077 not found; `um cp77 game \"<install folder>\"`")
    return p


# --------------------------------------------------------------------------- archives

def fnv1a64(s: str) -> int:
    h = FNV_OFFSET
    for b in s.encode("utf-8"):
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


def archive_hashes(path: Path) -> list[int]:
    """The path hashes (FNV1a64) of every file in a REDengine 4 .archive, read from its index table."""
    with open(path, "rb") as f:
        head = f.read(40)
        if len(head) < 40 or head[:4] != b"RDAR":
            raise Cp77Error(f"not a REDengine archive (no RDAR magic): {path}")
        _, _, index_pos, index_size, _, _, _ = struct.unpack("<4sIQIQIQ", head)
        f.seek(index_pos)
        _, _, _, n_entries, _, _ = struct.unpack("<IIQIII", f.read(28))
        raw = f.read(56 * n_entries)
    if len(raw) < 56 * n_entries:
        raise Cp77Error(f"truncated index in {path}")
    return [struct.unpack_from("<Q", raw, 56 * i)[0] for i in range(n_entries)]


def wolvenkit_cli() -> Path | None:
    cands = [config().get("wolvenkit"), os.environ.get("UM_WOLVENKIT"), shutil.which("WolvenKit.CLI"),
             Path.home() / "Tools" / "WolvenKit.Console" / "WolvenKit.CLI.exe",
             Path.home() / "Tools" / "WolvenKit.CLI" / "WolvenKit.CLI.exe"]
    for c in cands:
        if c and Path(c).is_file():
            return Path(c)
    return None


def archive_names(path: Path, cli: Path | None = None) -> dict[int, str]:
    """hash -> path for the files WolvenKit can name in this archive (it prints a bare number for the rest)."""
    cli = cli or wolvenkit_cli()
    if not cli:
        return {}
    try:
        r = subprocess.run([str(cli), "archiveinfo", "-l", str(path)], capture_output=True, timeout=600, **text_utf8())
    except (OSError, subprocess.SubprocessError):
        return {}
    out = {}
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line or line.isdigit() or "\\" not in line and "/" not in line:
            continue
        p = line.replace("/", "\\")  # the game hashes the backslash form of a resource path
        out[fnv1a64(p)] = p
    return out


def names_for(hashes: set[int], archives: list[Path]) -> dict[int, str]:
    """Resolve what we can: a cache under state_dir, then WolvenKit on each archive that still has unknowns."""
    cache_p = state_dir() / "names.json"
    cache = {int(k): v for k, v in _load("names.json").items()} if cache_p.exists() else {}
    out = {h: cache[h] for h in hashes if h in cache}
    missing = hashes - set(out)
    if missing and wolvenkit_cli():
        for a in archives:
            got = archive_names(a)
            out.update({h: p for h, p in got.items() if h in hashes})
            cache.update(got)
            missing -= set(got)
            if not missing:
                break
        if len(cache) < 2_000_000:
            _save("names.json", {str(k): v for k, v in cache.items()})
    return out


def label(h: int, names: dict[int, str]) -> str:
    return names.get(h) or f"hash {h:016x}"


# --------------------------------------------------------------------------- vanilla index

def vanilla_path() -> Path:
    return state_dir() / "vanilla-hashes.npy"


def build_vanilla_index(game: Path) -> int:
    import numpy as np
    hashes: set[int] = set()
    files = [p for d in VANILLA_DIRS for p in sorted((game / d).glob("*.archive"))]
    if not files:
        raise Cp77Error(f"no vanilla archives under {game}/archive/pc/content")
    for i, p in enumerate(files, 1):
        print(f"\r  {i}/{len(files)} {p.name:<40}", end="", file=sys.stderr, flush=True)
        hashes.update(archive_hashes(p))
    print(file=sys.stderr)
    arr = np.array(sorted(hashes), dtype=np.uint64)
    np.save(vanilla_path(), arr)
    return len(arr)


def vanilla_overrides(hashes: list[int]) -> int | None:
    """How many of these hashes exist in the vanilla archives, or None when the index was never built."""
    if not vanilla_path().exists() or not hashes:
        return None if not vanilla_path().exists() else 0
    import numpy as np
    arr = np.load(vanilla_path())
    return int(np.isin(np.array(hashes, dtype=np.uint64), arr).sum())


# --------------------------------------------------------------------------- load order

def load_order(game: Path) -> list[str]:
    """Archive names in the order the game loads them: modlist.txt entries first, then the rest by name."""
    d = game / MOD_DIR
    present = sorted((p.name for p in d.glob("*.archive")), key=lambda n: n.upper()) if d.is_dir() else []
    listed = []
    ml = d / "modlist.txt"
    if ml.is_file():
        for line in ml.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                name = line if line.lower().endswith(".archive") else line + ".archive"
                hit = next((p for p in present if p.lower() == name.lower()), None)
                if hit and hit not in listed:
                    listed.append(hit)
    return listed + [p for p in present if p not in listed]


# --------------------------------------------------------------------------- extraction

def seven_zip() -> str | None:
    for c in (shutil.which("7z"), shutil.which("7zz"), shutil.which("7za"),
              r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"):
        if c and Path(to_posix(c)).is_file():
            return c
    return None


def extract(archive: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    ext = archive.suffix.lower()
    if ext == ".zip":
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                target = (dest / info.filename).resolve()
                if dest.resolve() not in target.parents and target != dest.resolve():
                    raise Cp77Error(f"zip entry escapes the folder: {info.filename}")
            z.extractall(dest)
        return
    sz = seven_zip()
    if sz:
        r = subprocess.run([sz, "x", "-y", f"-o{dest}", str(archive)], capture_output=True, **text_utf8())
        if r.returncode == 0:
            return
        err = (r.stderr or r.stdout).strip()[-500:]
    else:
        err = "7-Zip not found (install it, or put 7z on PATH)"
    if ext == ".rar":
        for un in (shutil.which("unrar"), r"C:\Program Files\WinRAR\UnRAR.exe"):
            if un and Path(to_posix(un)).is_file():
                r = subprocess.run([un, "x", "-y", "-o+", str(archive), str(dest) + os.sep], capture_output=True, **text_utf8())
                if r.returncode == 0:
                    return
                err = (r.stderr or r.stdout).strip()[-500:]
    raise Cp77Error(f"could not extract {archive.name}: {err}")


# --------------------------------------------------------------------------- layout

def plan_layout(root: Path, modname: str, pick: str | None = None) -> tuple[list[tuple[Path, str]], list[str], list[str]]:
    """Where each extracted file goes under the game folder.

    Returns (placed [(source, game-relative dest)], skipped (readmes, previews), unplaced (unknown)).
    Known game folders are recognised at any depth (`MyMod/archive/pc/mod/x.archive` -> `archive/pc/mod/x.archive`);
    loose .archive/.xl files go to archive/pc/mod, loose .reds to r6/scripts/<mod>/, loose .yaml to r6/tweaks/<mod>/,
    a folder holding init.lua is a CET mod. `pick` limits the plan to one subfolder of the extraction (variants).
    """
    base = root
    if pick:
        cand = [d for d in root.rglob("*") if d.is_dir() and d.relative_to(root).as_posix().lower() == pick.replace("\\", "/").strip("/").lower()]
        if not cand:
            raise Cp77Error(f"--pick {pick!r}: no such folder in the download. Top-level folders: "
                            + ", ".join(sorted(d.name for d in root.iterdir() if d.is_dir())))
        base = cand[0]
    files = [p for p in sorted(base.rglob("*")) if p.is_file()]
    rel_of = {p: p.relative_to(base).parts for p in files}
    # pre-passes: REDmod folders (mods/*/info.json) and CET mod folders (init.lua)
    redmod_dirs = {p.parents[1] for p in files if p.name.lower() == "info.json" and len(p.parents) > 1 and p.parents[1].name.lower() == "mods"}
    cet_dirs = [p.parent for p in files if p.name.lower() == "init.lua" and not _known_root(rel_of[p])]
    placed, skipped, unplaced = [], [], []
    for p in files:
        parts = rel_of[p]
        if p.name.lower() in SKIP_NAMES:
            skipped.append("/".join(parts))
            continue
        dest = _known_root(parts, redmod_dirs, base)
        if dest is None and p.suffix.lower() in (".archive", ".xl"):
            dest = _loose(parts, modname)  # an archive next to a CET init.lua still belongs in archive/pc/mod
        if dest is None:
            for cd in cet_dirs:
                if cd == p.parent or cd in p.parents:
                    folder = cd.name if cd != base else modname
                    dest = f"{CET_MODS}/{folder}/{p.relative_to(cd).as_posix()}"
                    break
        if dest is None:
            dest = _loose(parts, modname)
        if dest is None:
            (skipped if p.suffix.lower() in SKIP_EXT else unplaced).append("/".join(parts))
            continue
        placed.append((p, dest))
    return placed, skipped, unplaced


def _known_root(parts: tuple[str, ...], redmod_dirs: set | None = None, base: Path | None = None) -> str | None:
    low = [x.lower() for x in parts]
    for i in range(len(parts) - 1):
        nxt = ROOTS.get(low[i])
        if low[i] not in ROOTS:
            continue
        if low[i] == "mods":
            if redmod_dirs is not None and base is not None and (base.joinpath(*parts[:i + 1]) in redmod_dirs):
                return "/".join(parts[i:])
            continue
        if nxt is None or low[i + 1] in nxt:
            return "/".join(parts[i:])
    return None


def _loose(parts: tuple[str, ...], modname: str) -> str | None:
    name = parts[-1]
    ext = Path(name).suffix.lower()
    if ext in (".archive", ".xl"):
        return f"{MOD_DIR}/{name}"
    if ext == ".reds":
        return f"r6/scripts/{modname}/{name}"
    if ext in (".yaml", ".yml", ".tweak"):
        return f"r6/tweaks/{modname}/{name}"
    return None


# --------------------------------------------------------------------------- install

def sanitize(name: str) -> str:
    return re.sub(r"[^\w .()'\-]+", "", name).strip(" .")[:80] or "mod"


def nexus_stem(stem: str) -> str:
    """'Better Trees-1234-2-0-1700000000' (Nexus file naming) -> 'Better Trees'."""
    return re.sub(r"-\d+(?:-[\w.]+)*?-\d{9,}$", "", stem) or stem


def _sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def owners(man: dict) -> dict[str, str]:
    return {rel: name for name, m in man["mods"].items() for rel in m.get("files", {})}


def install_paths(paths: list, name: str | None = None, pick: str | None = None, replace: bool = False,
                  overwrite: bool = False, dry: bool = False, ignore_unplaced: bool = False, file_id: int | None = None):
    """Install each source: a Nexus mod id, an nxm:// link, a downloaded archive, or an extracted folder."""
    from um import nexus
    game = game_dir()
    for src in paths:
        s = str(src)
        meta = None
        if s.isdigit() or s.startswith("nxm://"):
            key = nexus.nexus_key()
            try:
                if s.isdigit():
                    path, meta = nexus.fetch_file(GAME_DOMAIN, int(s), file_id, key)
                else:
                    link = nexus.parse_nxm(s)
                    if link["game"] != GAME_DOMAIN:
                        raise Cp77Error(f"that nxm link is for {link['game']}, not Cyberpunk 2077")
                    path, meta = nexus.fetch_file(link["game"], link["mod_id"], link["file_id"], key, nxm=link)
            except nexus.NexusError as e:
                raise Cp77Error(str(e))
        else:
            path = Path(to_posix(s)).expanduser()
            if not path.exists():
                raise Cp77Error(f"not found: {path}")
            sc = nexus.sidecar(path)
            if sc.exists():
                try:
                    meta = json.loads(sc.read_text(encoding="utf-8"))
                except ValueError:
                    meta = None
        install_one(game, path, name, pick, replace, overwrite, dry, ignore_unplaced, meta)


def install_one(game: Path, src: Path, name: str | None, pick: str | None, replace: bool, overwrite: bool,
                dry: bool, ignore_unplaced: bool, meta: dict | None):
    man = manifest()
    modname = sanitize(name or (meta or {}).get("mod_name") or nexus_stem(src.stem))
    if modname in man["mods"]:
        if not replace:
            raise Cp77Error(f"{modname!r} is already installed; --replace reinstalls it (uninstall first), --name picks another name")
        if not dry:
            uninstall(modname, force=True, quiet=True)
            man = manifest()
    tmp = state_dir() / "tmp" / sanitize(src.stem)
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        if src.is_dir():
            root = src
        else:
            extract(src, tmp)
            root = tmp
        placed, skipped, unplaced = plan_layout(root, modname, pick)
        # one destination from two sources: variants packed side by side
        by_dest: dict[str, list[Path]] = {}
        for p, d in placed:
            by_dest.setdefault(d.lower(), []).append(p)
        dupes = {d: ps for d, ps in by_dest.items() if len(ps) > 1}
        if dupes:
            lines = "\n".join(f"  {d}  <-  " + ", ".join(str(p.relative_to(root)) for p in ps) for d, ps in list(dupes.items())[:12])
            tops = ", ".join(sorted(d.name for d in root.iterdir() if d.is_dir()))
            raise Cp77Error(f"the download holds variants of the same file; choose one with --pick <folder>:\n{lines}\n"
                            f"top-level folders: {tops}")
        if unplaced and not ignore_unplaced:
            lines = "\n".join("  " + u for u in unplaced[:20])
            raise Cp77Error(f"{len(unplaced)} file(s) have no known place in the game folder:\n{lines}\n"
                            "Use --pick <folder> if these are variants, or --ignore-unplaced to leave them out")
        if not placed:
            raise Cp77Error("nothing to install: no game files found in the download")
        own = owners(man)
        taken = [(d, own[d]) for _, d in placed if d in own]
        existing = [d for _, d in placed if d not in own and (game / d).exists()]
        print(f"{modname}: {len(placed)} files" + (f", {len(skipped)} skipped (readme/previews)" if skipped else "")
              + (f", {len(unplaced)} ignored" if unplaced else ""))
        for _, d in placed[:40]:
            print(f"  {d}")
        if len(placed) > 40:
            print(f"  ... {len(placed) - 40} more")
        if taken:
            lines = "\n".join(f"  {d}  (installed by {o})" for d, o in taken[:12])
            raise Cp77Error(f"{len(taken)} file(s) already belong to other mods:\n{lines}\n"
                            "Uninstall that mod first, or --name a variant and --pick to avoid the clash")
        if existing and not overwrite:
            lines = "\n".join("  " + d for d in existing[:12])
            raise Cp77Error(f"{len(existing)} file(s) already exist in the game folder but no mod owns them "
                            f"(vanilla or hand-installed):\n{lines}\n--overwrite backs them up and replaces them")
        if dry:
            print("dry run: nothing copied")
            return
        entry = dict(installed=time.strftime("%Y-%m-%d %H:%M:%S"), source=str(src), nexus=meta, files={},
                     archives={}, replaced={}, skipped=skipped, ignored=unplaced)
        for p, d in placed:
            dest = game / d
            if d in existing:
                bk = state_dir() / "replaced" / modname / d
                bk.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, bk)
                entry["replaced"][d] = str(bk)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            entry["files"][d] = dict(sha1=_sha1(dest), size=dest.stat().st_size)
            if d.lower().endswith(".archive") and d.lower().startswith(MOD_DIR):
                entry["archives"][d] = archive_hashes(dest)
        man["mods"][modname] = entry
        _save("manifest.json", man)
        n_arch = len(entry["archives"])
        print(f"installed {modname}: {len(placed)} files, {n_arch} archive(s)" + (f", {len(existing)} replaced (backed up)" if existing else ""))
        if n_arch:
            report_conflicts(game, man, only=modname, show_paths=False, brief=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def uninstall(modname: str, force: bool = False, quiet: bool = False):
    game = game_dir()
    man = manifest()
    m = man["mods"].get(modname)
    if not m:
        close = [n for n in man["mods"] if modname.lower() in n.lower()]
        raise Cp77Error(f"not installed: {modname!r}" + (f"; did you mean {close}?" if close else ""))
    removed, kept, missing = 0, [], 0
    for rel, info in m["files"].items():
        p = game / rel
        if not p.exists():
            missing += 1
            continue
        if not force and _sha1(p) != info["sha1"]:
            kept.append(rel)
            continue
        p.unlink()
        removed += 1
        # tidy empty folders this mod created, but never the game's own structure
        d = p.parent
        while d != game and d.is_dir() and not any(d.iterdir()) and d.relative_to(game).as_posix().count("/") >= 2:
            d.rmdir()
            d = d.parent
    for rel, bk in m.get("replaced", {}).items():
        if Path(bk).exists():
            (game / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bk, game / rel)
    shutil.rmtree(state_dir() / "replaced" / modname, ignore_errors=True)
    if kept and not force:
        if not quiet:
            print(f"{modname}: removed {removed}, kept {len(kept)} file(s) changed since install (--force removes them too):")
            for k in kept[:10]:
                print("  " + k)
        m["files"] = {rel: m["files"][rel] for rel in kept}
        m["archives"] = {rel: h for rel, h in m.get("archives", {}).items() if rel in kept}
        man["mods"][modname] = m
    else:
        del man["mods"][modname]
    _save("manifest.json", man)
    if not quiet:
        print(f"uninstalled {modname}: {removed} files removed" + (f", {missing} were already gone" if missing else "")
              + (f", {len(m.get('replaced', {}))} restored" if m.get("replaced") else ""))


# --------------------------------------------------------------------------- reports

def archive_table(game: Path, man: dict) -> dict[str, tuple[str, list[int]]]:
    """archive file name -> (mod name or '(unmanaged)', hashes) for every .archive in archive/pc/mod."""
    table: dict[str, tuple[str, list[int]]] = {}
    for name, m in man["mods"].items():
        for rel, hashes in m.get("archives", {}).items():
            table[Path(rel).name] = (name, hashes)
    d = game / MOD_DIR
    if d.is_dir():
        for p in d.glob("*.archive"):
            if p.name not in table:
                try:
                    table[p.name] = ("(unmanaged)", archive_hashes(p))
                except Cp77Error:
                    table[p.name] = ("(unreadable)", [])
    return table


def report_conflicts(game: Path, man: dict, only: str | None = None, show_paths: bool = False, brief: bool = False):
    table = archive_table(game, man)
    order = load_order(game)
    rank = {n: i for i, n in enumerate(order)}
    sets = {n: set(h) for n, (_, h) in table.items()}
    names = sorted(table, key=lambda n: rank.get(n, 1 << 30))
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if only and only not in (table[a][0], table[b][0]):
                continue
            shared = sets[a] & sets[b]
            if shared:
                pairs.append((a, b, shared))
    if not brief:
        print(f"{len(table)} archives in {MOD_DIR}, load order (first wins):")
        for n in order:
            print(f"  {n}  [{table.get(n, ('?', []))[0]}]")
        vp = vanilla_path().exists()
        print()
        for n in names:
            if only and table[n][0] != only:
                continue
            ov = vanilla_overrides(table[n][1]) if vp else None
            ovs = f", overrides {ov} vanilla files" if ov is not None else ""
            print(f"{n}: {len(table[n][1])} files{ovs}  [{table[n][0]}]")
        if not vp:
            print("(run `um cp77 vanilla-index` once to see how many vanilla files each archive overrides)")
        print()
    if not pairs:
        print("no two archives touch the same path" if not only else f"{only}: no path shared with another archive")
        return
    for a, b, shared in pairs:
        winner = a if rank.get(a, 1 << 30) <= rank.get(b, 1 << 30) else b
        print(f"{a} [{table[a][0]}]  <->  {b} [{table[b][0]}]: {len(shared)} shared path(s), {winner} wins")
        if show_paths:
            nm = names_for(shared, [game / MOD_DIR / a, game / MOD_DIR / b])
            for h in sorted(shared, key=lambda h: nm.get(h, "~")):
                print("    " + label(h, nm))
    if brief:
        print("(`um cp77 conflicts --paths` lists the shared paths)")


def check(game: Path, man: dict):
    own = owners(man)
    changed, missing = [], []
    for name, m in man["mods"].items():
        for rel, info in m["files"].items():
            p = game / rel
            if not p.exists():
                missing.append(f"{rel}  ({name})")
            elif p.stat().st_size != info["size"] or _sha1(p) != info["sha1"]:
                changed.append(f"{rel}  ({name})")
    stray = []
    d = game / MOD_DIR
    if d.is_dir():
        stray += [f"{MOD_DIR}/{p.name}" for p in d.iterdir() if p.is_file() and p.suffix.lower() in (".archive", ".xl") and f"{MOD_DIR}/{p.name}" not in own]
    for sub in ("r6/scripts", "r6/tweaks", CET_MODS, "red4ext/plugins", "mods"):
        dd = game / sub
        if dd.is_dir():
            for p in dd.iterdir():
                prefix = f"{sub}/{p.name}"
                if p.name.startswith(".") or p.name.lower() in ("info.json",):
                    continue
                if not any(o == prefix or o.startswith(prefix + "/") for o in own):
                    stray.append(prefix + ("/" if p.is_dir() else ""))
    for title, rows in (("missing (deleted outside um)", missing), ("changed since install", changed), ("not recorded by um (hand-installed or leftovers)", stray)):
        print(f"{title}: {len(rows)}")
        for r in rows[:50]:
            print("  " + r)
    if not (missing or changed or stray):
        print("everything matches the manifest")


def updates(man: dict):
    from um import nexus
    key = nexus.nexus_key()
    seen = 0
    for name, m in man["mods"].items():
        meta = m.get("nexus")
        if not meta:
            continue
        seen += 1
        try:
            files = nexus.mod_files(meta["game"], meta["mod_id"], key)
        except nexus.NexusError as e:
            print(f"{name}: {e}")
            continue
        mains = [f for f in files if f.get("category_name") == "MAIN"] or files
        newest = max(mains, key=lambda f: f.get("uploaded_timestamp") or 0, default=None)
        mine = next((f for f in files if f.get("file_id") == meta.get("file_id")), None)
        if newest and newest.get("file_id") != meta.get("file_id") and (newest.get("uploaded_timestamp") or 0) > (meta.get("uploaded") or 0):
            print(f"{name}: v{meta.get('file_version')} -> v{newest.get('version')} ({newest.get('name')}, file {newest['file_id']}, "
                  f"{time.strftime('%Y-%m-%d', time.gmtime(newest.get('uploaded_timestamp') or 0))})"
                  f"\n    um cp77 install {meta['mod_id']} --file {newest['file_id']} --replace --name \"{name}\"")
        elif mine and mine.get("category_name") in ("OLD_VERSION", "ARCHIVED"):
            print(f"{name}: the installed file is now in {mine['category_name']}; `um nexus files {meta['mod_id']}`")
        else:
            print(f"{name}: up to date (v{meta.get('file_version')})")
    if not seen:
        print("no installed mod came from Nexus (`um cp77 install <mod id>` records the version)")
    print(nexus._limits_line())


def loaders(game: Path):
    for name, paths in LOADERS:
        have = [p for p in paths if (game / p).exists()]
        state = "installed" if len(have) == len(paths) else ("partial: " + ", ".join(have) if have else "absent")
        print(f"{name:<22} {state}")
    d = game / MOD_DIR
    n = len(list(d.glob("*.archive"))) if d.is_dir() else 0
    print(f"\n{MOD_DIR}: {n} archives; CET mods: {len(list((game / CET_MODS).iterdir())) if (game / CET_MODS).is_dir() else 0}; "
          f"redscript mods: {len(list((game / 'r6/scripts').iterdir())) if (game / 'r6/scripts').is_dir() else 0}")


# --------------------------------------------------------------------------- commands

def _run(fn, args):
    try:
        return fn(args)
    except Cp77Error as e:
        die(str(e))


def cmd_game(args):
    c = config()
    if args.path:
        p = Path(to_posix(args.path)).expanduser()
        if not _is_game(p):
            raise Cp77Error(f"no bin/x64/Cyberpunk2077.exe under {p}")
        c["game"] = str(p)
    if args.wolvenkit:
        w = Path(to_posix(args.wolvenkit)).expanduser()
        if not w.is_file():
            raise Cp77Error(f"not a file: {w}")
        c["wolvenkit"] = str(w)
    if args.path or args.wolvenkit:
        _save("config.json", c)
    g = game_dir()
    print(f"game       {g}  ({'configured' if c.get('game') else 'auto-detected'})")
    wk = wolvenkit_cli()
    print(f"wolvenkit  {wk or 'not found (conflict paths show as hashes; `um cp77 game --wolvenkit <WolvenKit.CLI.exe>`)'}")
    print(f"state      {state_dir()}")
    print(f"vanilla    {'indexed' if vanilla_path().exists() else 'not indexed (`um cp77 vanilla-index`)'}")


def cmd_install(args):
    if args.file is not None and len(args.source) != 1:
        raise Cp77Error("--file goes with a single mod id")
    install_paths(args.source, name=args.name, pick=args.pick, replace=args.replace, overwrite=args.overwrite,
                  dry=args.dry, ignore_unplaced=args.ignore_unplaced, file_id=args.file)


def cmd_list(args):
    man = manifest()
    if args.json:
        emit(man, True)
        return
    if not man["mods"]:
        print("no mods installed by um cp77")
        return
    for name, m in sorted(man["mods"].items(), key=lambda kv: kv[0].lower()):
        meta = m.get("nexus") or {}
        ver = f"v{meta.get('file_version')}" if meta.get("file_version") else ""
        src = f"nexus {meta['mod_id']}/{meta.get('file_id')}" if meta.get("mod_id") else Path(m.get("source", "")).name
        print(f"{name:<40} {ver:<10} {len(m['files']):>4} files {len(m.get('archives', {})):>3} archives  {m['installed'][:10]}  {src}")


def cmd_files(args):
    m = manifest()["mods"].get(args.name)
    if not m:
        raise Cp77Error(f"not installed: {args.name!r}")
    for rel in m["files"]:
        print(rel)
    for rel in m.get("replaced", {}):
        print(f"(replaced an existing file, backed up) {rel}")


def cmd_uninstall(args):
    for n in args.name:
        uninstall(n, force=args.force)


def cmd_conflicts(args):
    game = game_dir()
    report_conflicts(game, manifest(), only=args.name, show_paths=args.paths)


def cmd_check(args):
    check(game_dir(), manifest())


def cmd_hashes(args):
    p = Path(to_posix(args.archive)).expanduser()
    if not p.exists():
        p2 = game_dir() / MOD_DIR / args.archive
        if p2.exists():
            p = p2
        else:
            raise Cp77Error(f"not found: {args.archive}")
    hashes = archive_hashes(p)
    nm = names_for(set(hashes), [p]) if args.names else {}
    ov = vanilla_overrides(hashes)
    print(f"{p.name}: {len(hashes)} files" + (f", {ov} override vanilla" if ov is not None else "") + (f", {len(nm)} named" if args.names else ""))
    for h in hashes:
        print("  " + label(h, nm))


def cmd_vanilla(args):
    n = build_vanilla_index(game_dir())
    print(f"indexed {n:,} vanilla path hashes -> {vanilla_path()}")


def cmd_updates(args):
    updates(manifest())


def cmd_loaders(args):
    loaders(game_dir())


def register(sub):
    p = sub.add_parser("cp77", help="Cyberpunk 2077 mod manager: install from Nexus, track files, archive conflicts",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", metavar="<cmd>")

    g = s.add_parser("game", help="show or set the install folder and the WolvenKit CLI")
    g.add_argument("path", nargs="?")
    g.add_argument("--wolvenkit", help="path to WolvenKit.CLI.exe, for file names in conflict reports")
    g.set_defaults(func=lambda a: _run(cmd_game, a))

    i = s.add_parser("install", help="install Nexus mod ids, nxm:// links, downloaded archives or folders")
    i.add_argument("source", nargs="+", help="Nexus mod id, nxm:// link, .zip/.7z/.rar, or an extracted folder")
    i.add_argument("--file", type=int, help="Nexus file id (default: the primary main file)")
    i.add_argument("--name", help="name to record the mod under (default: the Nexus mod name)")
    i.add_argument("--pick", help="only install this subfolder of the download (variant packs)")
    i.add_argument("--replace", action="store_true", help="reinstall over a mod of the same name")
    i.add_argument("--overwrite", action="store_true", help="replace existing unowned files (backed up, restored on uninstall)")
    i.add_argument("--ignore-unplaced", action="store_true", help="skip files with no known destination instead of stopping")
    i.add_argument("--dry", action="store_true", help="show the plan, copy nothing")
    i.set_defaults(func=lambda a: _run(cmd_install, a))

    ls = s.add_parser("list", help="installed mods")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(func=lambda a: _run(cmd_list, a))

    f = s.add_parser("files", help="files a mod placed")
    f.add_argument("name")
    f.set_defaults(func=lambda a: _run(cmd_files, a))

    u = s.add_parser("uninstall", help="remove a mod's files, restore what it replaced")
    u.add_argument("name", nargs="+")
    u.add_argument("--force", action="store_true", help="also remove files changed since install")
    u.set_defaults(func=lambda a: _run(cmd_uninstall, a))

    c = s.add_parser("conflicts", help="archives that share paths, and who wins")
    c.add_argument("name", nargs="?", help="only this mod's archives")
    c.add_argument("--paths", action="store_true", help="list the shared paths (names via WolvenKit)")
    c.set_defaults(func=lambda a: _run(cmd_conflicts, a))

    k = s.add_parser("check", help="verify installed files; find archives nobody recorded")
    k.set_defaults(func=lambda a: _run(cmd_check, a))

    h = s.add_parser("hashes", help="list the path hashes in a .archive")
    h.add_argument("archive", help="path, or a file name in archive/pc/mod")
    h.add_argument("--names", action="store_true", help="resolve names with WolvenKit")
    h.set_defaults(func=lambda a: _run(cmd_hashes, a))

    v = s.add_parser("vanilla-index", help="index the vanilla archives' hashes (once per game patch)")
    v.set_defaults(func=lambda a: _run(cmd_vanilla, a))

    up = s.add_parser("updates", help="check Nexus for newer files of installed mods")
    up.set_defaults(func=lambda a: _run(cmd_updates, a))

    lo = s.add_parser("loaders", help="which loaders are present")
    lo.set_defaults(func=lambda a: _run(cmd_loaders, a))
