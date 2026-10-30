"""Check a mod folder before you share it: no game files, no decompiled code, no secrets, credits present.

    um publish check ./MyMod --game "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Terraria"

FAIL  files byte-identical to files in the game install (redistributing game files), leaked API keys
      (FAL_KEY, Anthropic, GitHub, AWS...), .env files. This mod's own installed copy (Mods/<Id>/,
      BepInEx/plugins/<name>/, named by Info.json, manifest.json or a .csproj) isn't compared; other mods are.
WARN  decompiler fingerprints in source (FUN_xxxx / DAT_xxxx / sub_XXXX, "// Decompiled with", ILSpy/dnSpy
      headers) - reimplement or reference instead of shipping decompiled code; big engine archives
      (.pak/.bsa/.ba2/.vpk/.rpf/.utoc...) that may carry original assets; absolute user paths; no README /
      credits; fal-generated assets listed in fal_manifest.jsonl without an attribution line
Modelled on IW4L's publish-check. It is a lint, not legal advice: when in doubt ship a patch/converter that
runs on the user's own install ("bring your own game files") instead of the files themselves.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from um.common import die, to_posix

SECRET_PATTERNS = [
    ("fal key", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[0-9a-f]{32}\b")),
    ("FAL_KEY assignment", re.compile(r"FAL_KEY\s*[=:]\s*['\"]?[A-Za-z0-9:_\-]{20,}")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("Sprixen key", re.compile(r"\bspx_live_[A-Za-z0-9_\-]{30,}")),
    # only as an assignment: a bare void_... is also an ordinary C identifier
    ("Voidless key", re.compile(r"VOIDLESS_API_KEY\s*[=:]\s*['\"]?void_[A-Za-z0-9_\-]{16,}")),
    # project, service-account and admin keys carry - and _ in their body; legacy keys are plain alphanumerics
    ("OpenAI key", re.compile(r"\bsk-(?:(?:proj|svcacct|admin)-[A-Za-z0-9_\-]{32,}|[A-Za-z0-9]{32,})")),
    # classic tokens (ghp_, gho_, ...) and fine-grained personal access tokens (github_pat_)
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})")),
    ("AWS key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]
DECOMP_PATTERNS = [
    ("Ghidra auto-name", re.compile(r"\b(?:FUN|DAT|LAB|PTR)_[0-9a-fA-F]{6,}\b")),
    ("IDA auto-name", re.compile(r"\b(?:sub|loc|unk|off|dword|qword)_[0-9A-F]{5,}\b")),
    ("decompiler header", re.compile(r"^\s*(?://|#|--|;)\s*(?:Decompiled with|Decompiler:|ILSpy|dnSpy|JetBrains decompiler)|^#region Assembly ", re.I | re.M)),
]
CODE_EXT = {".cs", ".c", ".cpp", ".h", ".hpp", ".py", ".lua", ".js", ".ts", ".rs", ".java", ".kt", ".gd", ".rpy", ".psc", ".gml",
            ".hlsl", ".glsl", ".as", ".vb", ".il"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "obj", ".vs", ".idea"}
TEXT_EXT = {".cs", ".c", ".cpp", ".h", ".hpp", ".py", ".lua", ".js", ".ts", ".json", ".toml", ".ini", ".cfg", ".txt", ".md", ".xml",
            ".yaml", ".yml", ".rs", ".java", ".kt", ".gd", ".rpy", ".psc", ".sh", ".ps1", ".bat", ".gml", ".hlsl", ".glsl", ".env"}
ARCHIVE_EXT = {".pak", ".utoc", ".ucas", ".bsa", ".ba2", ".vpk", ".rpf", ".pck", ".assets", ".bundle", ".sga", ".big", ".wad", ".bdt", ".archive"}


def _sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _own_names(files: list[Path]) -> set[str]:
    """Names a loader would install this mod under, from the mod's own metadata only: Info.json Id and
    AssemblyName (Unity Mod Manager), manifest.json name (Thunderstore), and the assembly a .csproj builds
    (<AssemblyName>, else the project's file name; BepInEx plugins). Other DLLs in the mod (game references,
    other mods it depends on) don't count, so their installed folders are still compared. Lower-cased."""
    import json
    names = set()
    for f in files:
        n = f.name.lower()
        try:
            if n.endswith(".csproj"):
                m = re.search(r"<AssemblyName>\s*([^<]+?)\s*</AssemblyName>", f.read_text(encoding="utf-8-sig", errors="replace"))
                names.add((m.group(1) if m and "$(" not in m.group(1) else f.stem).lower())
            elif n in ("info.json", "manifest.json"):
                d = json.loads(f.read_text(encoding="utf-8-sig", errors="replace"))
                for k in ("Id", "AssemblyName") if n == "info.json" else ("name",):
                    v = d.get(k) if isinstance(d, dict) else None
                    if isinstance(v, str) and v.strip():
                        names.add(re.sub(r"\.dll$", "", v.strip(), flags=re.I).lower())
        except (OSError, ValueError):
            continue
    return names


def _loader_folder(rel: tuple[str, ...]) -> tuple[str, str] | None:
    """(game-relative path, mod name) when a game-relative file path is in a loader's mods folder: Mods/<name>/...,
    BepInEx/plugins/<name>/..., or a plugin DLL directly in BepInEx/plugins/ (named by its stem). Else None."""
    low = [x.lower() for x in rel]
    for i in range(len(low) - 1):
        bep = low[i] == "plugins" and i > 0 and low[i - 1] == "bepinex"
        if i + 2 < len(low) and (low[i] == "mods" or bep):      # <name>/ and a file below it
            return "/".join(rel[:i + 2]) + "/", low[i + 1]
        if bep and i + 2 == len(low) and low[-1].endswith(".dll"):
            return "/".join(rel), low[-1][:-4]
    return None


def check(mod: str, game: str | None = None) -> int:
    root = Path(to_posix(mod))
    if not root.is_dir():
        die(f"not a folder: {root}")
    fails, warns = [], []
    files = [p for p in root.rglob("*") if p.is_file() and not SKIP_DIRS.intersection(p.relative_to(root).parts)]
    # game files, matched by size then hash
    if game:
        g = Path(to_posix(game))
        gr, mine = g.resolve(), root.resolve()
        # a mod inside the install (Dwarf Fortress mods/<name>) is not game content: don't match it against itself
        inside = mine.relative_to(gr).parts if mine != gr and mine.is_relative_to(gr) else None
        by_size: dict[int, list[Path]] = {}
        for p in g.rglob("*"):
            if inside and p.relative_to(g).parts[:len(inside)] == inside:
                continue
            if p.is_file():
                try:
                    by_size.setdefault(p.stat().st_size, []).append(p)
                except OSError:
                    pass
        # this mod installed into the game (Mods/<Id>/, BepInEx/plugins/<name>/) matches itself: skip that copy,
        # and say which folders were skipped
        own, skipped = _own_names(files), set()
        for sz, ps in list(by_size.items()):
            keep = []
            for p in ps:
                hit = _loader_folder(p.relative_to(g).parts)
                if hit and hit[1] in own:
                    skipped.add(hit[0])
                else:
                    keep.append(p)
            by_size[sz] = keep
        if skipped:
            print("note: not compared, this mod's own installed copy:", ", ".join(sorted(skipped)))
        for f in files:
            sz = f.stat().st_size
            if sz < 64 or sz not in by_size:
                continue
            h = _sha1(f)
            for gp in by_size[sz]:
                if _sha1(gp) == h:
                    fails.append(f"game file copied verbatim: {f.relative_to(root).as_posix()}  (== {gp.relative_to(g).as_posix()})")
                    break
    for f in files:
        rel = f.relative_to(root).as_posix()        # same report on every OS (Windows would print src\Mod.cs)
        if f.name == ".env" or f.name.endswith(".env"):
            fails.append(f"env file (secrets?): {rel}")
        if f.suffix.lower() in ARCHIVE_EXT and f.stat().st_size > 5 << 20:
            warns.append(f"large engine archive ({f.stat().st_size >> 20} MB): {rel} - make sure it holds only your own assets")
        if f.suffix.lower() in TEXT_EXT or f.name in (".env",):
            try:
                txt = f.read_text(errors="replace")
            except OSError:
                continue
            for label, rx in SECRET_PATTERNS:
                if rx.search(txt):
                    fails.append(f"{label} in {rel}")
            for label, rx in DECOMP_PATTERNS if f.suffix.lower() in CODE_EXT else ():
                m = rx.findall(txt)
                if m:
                    warns.append(f"{label} x{len(m)} in {rel} (e.g. {m[0].strip()!r})")
            if re.search(r"[A-Z]:\\Users\\[^\\\s\"']+|/home/[a-z_][a-z0-9_-]*/|/Users/[A-Za-z]+/", txt):
                warns.append(f"absolute user path in {rel}")
    names = {f.name.lower() for f in files}
    if not any(n.startswith("readme") for n in names):
        warns.append("no README (install steps, requirements, credits)")
    manifests = [f for f in files if f.name == "fal_manifest.jsonl"]
    if manifests:
        readmes = [f for f in files if f.name.lower().startswith(("readme", "credits"))]
        if not any("fal" in f.read_text(errors="replace").lower() for f in readmes):
            warns.append("fal-generated assets (fal_manifest.jsonl) but no credit line in README/CREDITS")
    for x in fails:
        print("FAIL ", x)
    for x in warns:
        print("WARN ", x)
    print(f"{'FAIL' if fails else 'WARN' if warns else 'PASS'}: {len(files)} files, {len(fails)} failures, {len(warns)} warnings")
    return 1 if fails else 0


def main(a):
    raise SystemExit(check(a.mod, a.game))


def register(sub):
    import argparse
    p = sub.add_parser("publish", help="lint a mod folder before sharing (game files, decompiled code, secrets)",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")
    q = cs.add_parser("check", help="check a mod folder")
    q.add_argument("mod")
    q.add_argument("--game", help="game install folder, to catch copied game files")
    q.set_defaults(func=main)
