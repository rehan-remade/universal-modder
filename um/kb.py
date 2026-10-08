"""The knowledge base: field notes on how games were actually modded, written by agents for agents.

    um kb search "unreal pak mod"               # prior art before you start (local repo, or synced from GitHub)
    um kb search terraria --route loader-api    # filter by game / engine / route
    um kb show games/terraria/fal-arsenal.md
    um kb new --game "Hades II" --title "A new boon god" --from-scan "hades"   # scaffold a note, pre-filled
    um kb check knowledge/games/hades-ii/new-boon-god.md                       # validate before a PR
    um kb index                                  # regenerate knowledge/INDEX.md + index.json
    um kb sync                                   # refresh the cached copy from GitHub
    um kb pr knowledge/games/hades-ii/new-boon-god.md --yes                     # branch, commit, push to your fork, open a PR

Every note is Markdown with YAML front matter (knowledge/TEMPLATE.md). `check` enforces the schema, the
required sections, no secrets, no pasted decompiled code, no huge files. Contributions go through pull
requests: that's how one agent's hard-won gotchas reach the next one. Ask your human before `um kb pr --yes`.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

from um.common import data_dir, die

REPO = os.environ.get("UM_KB_REPO", "rehan-remade/universal-modder")
BRANCH = os.environ.get("UM_KB_BRANCH", "main")
ROUTES = ["data", "asset-only", "loader-api", "managed-patch", "native-hook", "reimplementation", "decomp-recomp",
          "passthrough", "emulator", "other"]
STATUSES = ["idea", "in-progress", "working", "released", "abandoned"]
PLATFORMS = ["windows", "linux", "macos", "proton", "emulator", "console", "other"]
GAME_KEYS = ["kind", "title", "game", "engine", "route", "status", "date", "agents"]
TECH_KEYS = ["kind", "title", "tags", "date", "agents"]
GAME_SECTIONS = ["setup", "route", "verification", "gotchas"]
MAX_BLOCK_WARN, MAX_BLOCK_FAIL = 60, 150
MAX_NOTE_KB, MAX_MEDIA_MB = 120, 1.5
# Notes and the index are UTF-8 with \n line ends on every OS. Without this, Windows reads and writes them in its
# ANSI code page with \r\n: the index's "·" separators come out as invalid UTF-8 and `um kb check --index` fails.
TEXT = {"encoding": "utf-8", "newline": "\n"}


# --------------------------------------------------------------------------- where the notes are

def local_root() -> Path | None:
    """knowledge/ of the repo this package runs from (clone, plugin, editable install), or of the cwd's repo."""
    here = Path(__file__).resolve().parents[1] / "knowledge"
    if (here / "TEMPLATE.md").exists():
        return here
    for d in [Path.cwd(), *Path.cwd().parents]:
        if (d / "knowledge" / "TEMPLATE.md").exists():
            return d / "knowledge"
    return None


def cache_root() -> Path:
    return data_dir() / "kb" / REPO.replace("/", "__") / "knowledge"


def sync(quiet: bool = False) -> Path:
    """Mirror knowledge/ from GitHub into the cache (git tree API + raw files; no auth needed)."""
    api = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
    req = urllib.request.Request(api, headers={"User-Agent": "universal-modder", "Accept": "application/vnd.github+json"})
    tree = json.load(urllib.request.urlopen(req, timeout=60))
    paths = [t["path"] for t in tree.get("tree", []) if t["type"] == "blob" and t["path"].startswith("knowledge/")
             and t["path"].endswith((".md", ".json"))]
    root = cache_root()
    tmp = root.with_name("knowledge.tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    for p in paths:
        dst = tmp / p[len("knowledge/"):]
        dst.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{p}"
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "universal-modder"}), timeout=60) as r:
            dst.write_bytes(r.read())
    shutil.rmtree(root, ignore_errors=True)
    tmp.rename(root)
    (root / ".synced").write_text(str(time.time()), **TEXT)
    if not quiet:
        print(f"synced {len(paths)} files from github.com/{REPO} -> {root}")
    return root


def resolve_root(explicit: str | None = None, remote: bool = False) -> Path:
    if explicit:
        return Path(explicit)
    if os.environ.get("UM_KB"):
        return Path(os.environ["UM_KB"])
    loc = None if remote else local_root()
    if loc:
        return loc
    root = cache_root()
    stamp = root / ".synced"
    stale = not stamp.exists() or time.time() - float(stamp.read_text(encoding="utf-8") or 0) > 86400
    if stale:
        try:
            return sync(quiet=True)
        except OSError as e:
            if not root.exists():
                die(f"no local knowledge/ and GitHub sync failed ({e}); clone https://github.com/{REPO}")
    return root


# --------------------------------------------------------------------------- notes

def parse(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    import yaml
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except (yaml.YAMLError, ValueError) as e:  # ValueError: a date YAML can't build, e.g. 2026-09-31
        return {"_yaml_error": str(e)}, m.group(2)
    return (meta if isinstance(meta, dict) else {}), m.group(2)


def notes(root: Path) -> list[tuple[Path, dict, str]]:
    out = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        if rel in ("README.md", "INDEX.md", "TEMPLATE.md") or rel.startswith("engines/"):
            continue
        meta, body = parse(p)
        out.append((p, meta, body))
    return out


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "note"


# --------------------------------------------------------------------------- search

def _term(t: str) -> re.Pattern:
    """A search term that must start a word: "rust" finds "Rust" and "rusty", not "trust" or "frustum".
    A term that starts with punctuation (".esp", ".net") still matches anywhere, so it finds "plugin.esp"."""
    return re.compile((r"(?<![a-z0-9])" if t[:1].isalnum() else "") + re.escape(t))


def search(root: Path, terms: list[str], game=None, engine=None, route=None, limit=10) -> list[dict]:
    terms = [_term(t.lower()) for t in terms if t.strip()]
    res = []
    for p, meta, body in notes(root):
        if game and slug(game) not in slug(str(meta.get("game", ""))) + " " + " ".join(slug(g) for g in meta.get("games_also") or []):
            continue
        if engine and str(meta.get("engine", "")).lower() != engine.lower():
            continue
        if route and str(meta.get("route", "")).lower() != route.lower():
            continue
        fields = {
            5: str(meta.get("title", "")),
            4: " ".join([str(meta.get("game", ""))] + [str(g) for g in meta.get("games_also") or []]),
            3: " ".join(str(x) for x in [meta.get("engine", ""), meta.get("route", ""), *(meta.get("tags") or []), *(meta.get("tools") or [])]),
        }
        low = body.lower()
        score = 0
        for t in terms:
            score += sum(w for w, f in fields.items() if t.search(f.lower()))
            score += min(5, len(t.findall(low)))
        if terms and score == 0:
            continue
        hits = [ln.strip() for ln in body.splitlines() if ln.strip() and any(t.search(ln.lower()) for t in terms)][:3]
        res.append(dict(score=score, path=p.relative_to(root).as_posix(), title=meta.get("title"), game=meta.get("game"),
                        engine=meta.get("engine"), route=meta.get("route"), status=meta.get("status"), hits=hits))
    res.sort(key=lambda r: -r["score"])
    return res[:limit]


# --------------------------------------------------------------------------- check

def check_note(path: Path, root: Path | None = None) -> tuple[list[str], list[str]]:
    from um.publish import DECOMP_PATTERNS, SECRET_PATTERNS
    fails, warns = [], []
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse(path)
    if not meta:
        return [f"{path}: no YAML front matter (start the file with --- ... --- ; see knowledge/TEMPLATE.md)"], []
    if "_yaml_error" in meta:
        return [f"{path}: front matter is not valid YAML: {meta['_yaml_error']}"], []
    kind = meta.get("kind", "game")
    for k in GAME_KEYS if kind == "game" else TECH_KEYS:
        if meta.get(k) in (None, "", []):
            fails.append(f"missing front-matter key: {k}")
    if kind not in ("game", "technique"):
        fails.append(f"kind must be game or technique, not {kind!r}")
    if kind == "game":
        if meta.get("route") and meta["route"] not in ROUTES:
            fails.append(f"route {meta['route']!r} not one of: {', '.join(ROUTES)}")
        if meta.get("platform") and meta["platform"] not in PLATFORMS:
            warns.append(f"platform {meta['platform']!r} not one of: {', '.join(PLATFORMS)}")
        from um.scan import ENGINES
        if meta.get("engine") and meta["engine"] not in ENGINES and meta["engine"] != "unknown":
            warns.append(f"engine {meta['engine']!r} isn't one of um scan's keys ({', '.join(sorted(ENGINES))}, unknown)")
        heads = [h.lower() for h in re.findall(r"^##\s+(.+)$", body, re.M)]
        for s in GAME_SECTIONS:
            if not any(h.startswith(s) for h in heads):
                fails.append(f"missing section: ## {s.capitalize()}...")
        if "gotchas" in " ".join(heads) and not re.search(r"^##\s+Gotchas.*?\n(?:.*\n)*?\s*1\.", body, re.M | re.I):
            warns.append("Gotchas section has no numbered items")
    if meta.get("status") and meta["status"] not in STATUSES:
        fails.append(f"status {meta['status']!r} not one of: {', '.join(STATUSES)}")
    d = meta.get("date")
    if d and not isinstance(d, dt.date) and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(d)):
        fails.append(f"date must be YYYY-MM-DD, got {d!r}")
    if not isinstance(meta.get("agents", []), list):
        fails.append("agents must be a list, e.g. [\"Codex (gpt-6)\"]")
    if "Homing missiles and a tactical nuke in Terraria" == meta.get("title") and "TEMPLATE" not in path.name:
        fails.append("title is still the template's example title")
    left = [ph for ph in ("FILL IN", "Two to four sentences:", "Numbered; each one symptom", "What you saw. **Cause:** what it really was")
            if ph in text]
    if left and "TEMPLATE" not in path.name:
        fails.append(f"unfilled template text: {', '.join(repr(x) for x in left)}")
    for label, rx in SECRET_PATTERNS:
        if rx.search(text):
            fails.append(f"{label} in the note - remove it")
    blocks = re.findall(r"```[^\n]*\n(.*?)```", body, re.S)
    for b in blocks:
        n = b.count("\n")
        if n > MAX_BLOCK_FAIL:
            fails.append(f"a {n}-line code block: link to your repo instead of pasting code (limit {MAX_BLOCK_FAIL})")
        elif n > MAX_BLOCK_WARN:
            warns.append(f"a {n}-line code block: keep snippets short (under {MAX_BLOCK_WARN} lines)")
        for label, rx in DECOMP_PATTERNS:
            if rx.search(b):
                warns.append(f"{label} in a code block: describe decompiled logic, don't paste it")
    if re.search(r"[A-Z]:\\Users\\(?!<)[^\\\s`\"']+|/home/(?!<)[a-z_][a-z0-9_-]*/|/Users/(?!<)[A-Za-z]+/", text):
        warns.append("absolute user path (use <you>, %USERPROFILE% or ~ instead)")
    if len(text.encode()) > MAX_NOTE_KB * 1024:
        warns.append(f"note is {len(text.encode()) // 1024} KB; split it or trim (limit {MAX_NOTE_KB} KB)")
    for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)\)", body):
        src = m.group(1)
        if src.startswith("http"):
            continue
        img = (path.parent / src).resolve()
        if not img.exists():
            fails.append(f"image not found: {src}")
        elif img.stat().st_size > MAX_MEDIA_MB * 2**20:
            fails.append(f"image {src} is {img.stat().st_size / 2**20:.1f} MB (limit {MAX_MEDIA_MB} MB; link videos instead)")
    return fails, warns


# --------------------------------------------------------------------------- index

def build_index(root: Path) -> tuple[str, list[dict]]:
    rows = []
    for p, meta, _ in notes(root):
        rows.append(dict(path=p.relative_to(root).as_posix(), **{k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in meta.items()}))
    games = sorted([r for r in rows if r.get("kind", "game") == "game"], key=lambda r: (str(r.get("game", "")).lower(), str(r.get("date", ""))))
    techs = sorted([r for r in rows if r.get("kind") == "technique"], key=lambda r: str(r.get("title", "")).lower())
    def esc(s):
        return str(s or "").replace("|", "\\|")
    lines = ["# Knowledge base index", "",
             "_Generated by `um kb index` from the notes' front matter; don't edit by hand. Machine-readable: `index.json`._", "",
             f"## Games ({len(games)} notes)", "",
             "| Game | Note | Engine | Route | Status | Agents | Date |", "|---|---|---|---|---|---|---|"]
    for r in games:
        g = esc(r.get("game")) + (" + " + ", ".join(esc(x) for x in r.get("games_also") or []) if r.get("games_also") else "")
        lines.append(f"| {g} | [{esc(r.get('title'))}]({r['path']}) | {esc(r.get('engine'))} | {esc(r.get('route'))} | "
                     f"{esc(r.get('status'))} | {esc(', '.join(r.get('agents') or []))} | {esc(r.get('date'))} |")
    lines += ["", f"## Techniques ({len(techs)} notes)", ""]
    for r in techs:
        lines.append(f"- [{esc(r.get('title'))}]({r['path']}) · {esc(', '.join(r.get('tags') or []))}")
    lines += ["", "## Engine playbooks", "",
              "Per-engine routes and tools live with the skills: "
              "[skills/mod-any-game/references/engines/](../skills/mod-any-game/references/engines/).", ""]
    return "\n".join(lines), rows


# --------------------------------------------------------------------------- new / pr

def new_note(root: Path, game: str | None, title: str, kind: str = "game", from_scan: str | None = None,
             engine: str | None = None, route: str | None = None, agent: str | None = None, out: str | None = None) -> Path:
    import yaml
    meta, body = parse(root / "TEMPLATE.md")
    meta = {k: v for k, v in meta.items()}
    meta.update(kind=kind, title=title, date=dt.date.today().isoformat(), agents=[agent or os.environ.get("UM_AGENT", "FILL IN: agent (model)")],
                humans=[], links=[], tags=[], status="in-progress")
    if kind == "game":
        meta.update(game=game or "FILL IN", games_also=[], engine=engine or "unknown", route=route or "other", tools=[],
                    game_version="FILL IN: exact build", platform="windows", anti_cheat="FILL IN")
        if from_scan:
            from um.scan import scan
            s = scan(from_scan)
            meta.update(game=game or s["name"], engine=s["engine"]["key"],
                        anti_cheat=", ".join(s["anti_cheat"]) or "none found by um scan",
                        game_version=f"FILL IN ({s.get('store') or 'store?'} {s.get('appid') or ''})".strip(),
                        tools=s["mod_loaders_installed"])
    else:
        for k in ("game", "games_also", "game_version", "platform", "engine", "route", "tools", "anti_cheat"):
            meta.pop(k, None)
    body = re.sub(r"^# .*$", f"# {title}", body, count=1, flags=re.M)
    if kind == "technique":
        body = (f"# {title}\n\n> What this technique is for, in two sentences.\n\n## When to use it\n\n## How\n\n"
                "## Gotchas\n1. **Symptom.** ... **Cause:** ... **Fix:** ...\n\n## Seen in\nLinks to game notes that used it.\n")
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=120)
    base = root / ("games" / Path(slug(meta.get("game", "misc"))) if kind == "game" else Path("techniques"))
    path = Path(out) if out else base / f"{slug(title)}.md"
    if path.exists():
        die(f"{path} exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front}---\n{body}", **TEXT)
    return path


def pr_head(branch: str, fork_url: str | None) -> str:
    """The --head for `gh pr create`. gh looks a bare branch name up in the base repo, so a PR from a fork needs
    "<fork owner>:<branch>" (else: "Head ref must be a branch"). fork_url: the fork remote's URL, None when pushing
    to the repo itself."""
    remote = _github_remote(fork_url or "")
    return f"{remote[0]}:{branch}" if remote else branch


def _git_paths(repo: Path, *args: str) -> set[str]:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if r.returncode:
        die(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()[-800:]}")
    return {line for line in r.stdout.splitlines() if line}


def _validate_pr_worktree(repo: Path, allowed: set[str]) -> None:
    staged = _git_paths(repo, "diff", "--cached", "--name-only")
    if staged:
        die("refusing to create a PR with pre-staged files: " + ", ".join(sorted(staged)))
    dirty = _git_paths(repo, "diff", "--name-only") | _git_paths(repo, "ls-files", "--others", "--exclude-standard")
    unexpected = dirty - allowed
    if unexpected:
        die("refusing to mix unrelated worktree changes into the PR: " + ", ".join(sorted(unexpected)))


def _github_remote(url: str) -> tuple[str, str] | None:
    value = url.strip()
    scp = re.fullmatch(r"(?:git@)?github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?", value)
    if scp:
        return scp.group(1), scp.group(2)
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme not in {"https", "ssh"} or parsed.hostname != "github.com" or parsed.port is not None:
            return None
        if parsed.query or parsed.fragment or (parsed.scheme == "https" and (parsed.username or parsed.password)):
            return None
        if parsed.scheme == "ssh" and parsed.username not in {None, "git"}:
            return None
        match = re.fullmatch(r"/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", parsed.path)
        return (match.group(1), match.group(2)) if match else None
    except (TypeError, ValueError):
        return None


def _validate_fork_url(url: str, expected_owner: str | None = None) -> None:
    remote = _github_remote(url)
    if not remote or remote[1] != "universal-modder":
        die(f"fork remote does not target a GitHub universal-modder repository: {url}")
    if expected_owner and remote[0].lower() != expected_owner.lower():
        die(f"fork remote owner {remote[0]!r} does not match authenticated GitHub user {expected_owner!r}")


def _validate_upstream_url(url: str) -> None:
    remote = _github_remote(url)
    expected = tuple(REPO.split("/", 1))
    if remote != expected:
        die(f"origin remote {remote!r} does not match configured knowledge repository {expected!r}")


def _ensure_branch_absent(repo: Path, branch: str) -> None:
    result = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo)
    if result.returncode == 0:
        die(f"refusing to replace or delete pre-existing local branch: {branch}")
    if result.returncode != 1:
        die(f"could not verify local branch absence: {branch}")


def _delete_branch_if_owned(repo: Path, branch: str, expected_oid: str) -> bool:
    current = subprocess.run(["git", "rev-parse", "--verify", f"refs/heads/{branch}"], cwd=repo,
                             capture_output=True, text=True)
    if current.returncode or current.stdout.strip() != expected_oid:
        return False
    deleted = subprocess.run(["git", "branch", "-D", branch], cwd=repo, capture_output=True, text=True)
    return deleted.returncode == 0


def _publish_pr_isolated(repo: Path, root: Path, contribution: list[Path], branch: str, title: str,
                         body: str, can_push: bool, note_rel: str) -> str:
    """Build and publish the contribution from a disposable worktree; never mutate the caller's checkout."""
    remote = "origin" if can_push else "fork"
    fork_url = None
    if not can_push:
        remote_url = subprocess.run(["git", "remote", "get-url", "fork"], cwd=repo, capture_output=True, text=True)
        if remote_url.returncode:
            result = subprocess.run(["gh", "repo", "fork", "--remote", "--remote-name", "fork"], cwd=repo,
                                    capture_output=True, text=True)
            if result.returncode:
                die(f"gh repo fork failed: {(result.stderr or result.stdout).strip()[-800:]}")
            remote_url = subprocess.run(["git", "remote", "get-url", "fork"], cwd=repo, capture_output=True, text=True)
        fork_url = remote_url.stdout.strip()
        who = subprocess.run(["gh", "api", "user", "--jq", ".login"], cwd=repo, capture_output=True, text=True)
        if who.returncode or not who.stdout.strip():
            die(f"could not verify authenticated GitHub identity: {(who.stderr or who.stdout).strip()[-800:]}")
        _validate_fork_url(fork_url, who.stdout.strip())
    else:
        origin_url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo, capture_output=True, text=True)
        if origin_url.returncode:
            die("could not read origin remote before push")
        _validate_upstream_url(origin_url.stdout.strip())

    temp_root = Path(tempfile.mkdtemp(prefix="um-kb-worktree-"))
    worktree = temp_root / "repo"
    added = subprocess.run(["git", "worktree", "add", "--detach", str(worktree), "HEAD"], cwd=repo,
                           capture_output=True, text=True)
    if added.returncode:
        shutil.rmtree(temp_root, ignore_errors=True)
        die(f"could not create isolated worktree: {(added.stderr or added.stdout).strip()[-800:]}")
    success = branch_created = False
    branch_tip: str | None = None
    try:
        work_root = worktree / root.relative_to(repo)
        staged_paths = []
        for source in contribution:
            relative = source.relative_to(repo)
            destination = worktree / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
            staged_paths.append(destination)
        result = subprocess.run(["git", "checkout", "-b", branch], cwd=worktree, capture_output=True, text=True)
        if result.returncode:
            die(f"git checkout -b failed: {(result.stderr or result.stdout).strip()[-800:]}")
        branch_created = True
        branch_tip = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, text=True).strip()
        idx, rows = build_index(work_root)
        index_md, index_json = work_root / "INDEX.md", work_root / "index.json"
        index_md.write_text(idx, **TEXT)
        index_json.write_text(json.dumps(rows, indent=1, default=str) + "\n", **TEXT)
        staged_paths += [index_md, index_json]
        allowed = {str(p.relative_to(worktree)) for p in staged_paths}
        result = subprocess.run(["git", "add", "--", *map(str, staged_paths)], cwd=worktree, capture_output=True, text=True)
        if result.returncode:
            die(f"git add failed: {(result.stderr or result.stdout).strip()[-800:]}")
        staged = _git_paths(worktree, "diff", "--cached", "--name-only")
        unexpected = staged - allowed
        if unexpected or note_rel not in staged:
            die("staged diff escaped the approved contribution set: " + ", ".join(sorted(unexpected)))
        result = subprocess.run(["git", "commit", "-m", title], cwd=worktree, capture_output=True, text=True)
        if result.returncode:
            die(f"git commit failed: {(result.stderr or result.stdout).strip()[-800:]}")
        branch_tip = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, text=True).strip()
        result = subprocess.run(["git", "push", "-u", remote, branch], cwd=worktree, capture_output=True, text=True)
        if result.returncode:
            die(f"git push failed: {(result.stderr or result.stdout).strip()[-800:]}")
        local_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=worktree, capture_output=True, text=True,
                                   check=True).stdout.strip()
        remote_result = subprocess.run(["git", "ls-remote", remote, f"refs/heads/{branch}"], cwd=worktree,
                                       capture_output=True, text=True, check=True)
        remote_sha = remote_result.stdout.split("\t", 1)[0]
        if local_sha != remote_sha:
            die("pushed branch SHA did not match the local commit")
        head = pr_head(branch, fork_url)
        result = subprocess.run(["gh", "pr", "create", "--repo", REPO, "--head", head, "--title", title, "--body", body],
                                cwd=worktree, capture_output=True, text=True)
        if result.returncode:
            die(f"gh pr create failed: {(result.stderr or result.stdout).strip()[-800:]}")
        pr_url = result.stdout.strip().splitlines()[-1]
        readback = subprocess.run(["gh", "pr", "view", pr_url, "--repo", REPO, "--json", "headRefOid", "--jq", ".headRefOid"],
                                  cwd=worktree, capture_output=True, text=True)
        if readback.returncode or readback.stdout.strip() != local_sha:
            die("created PR head did not read back at the pushed commit")
        success = True
        return pr_url
    finally:
        removed = subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo,
                                 capture_output=True, text=True)
        if removed.returncode:
            print(f"warning: could not unregister temporary worktree: {(removed.stderr or removed.stdout).strip()[-800:]}",
                  file=sys.stderr)
        else:
            shutil.rmtree(temp_root, ignore_errors=True)
        if not success and branch_created and branch_tip is not None:
            if not _delete_branch_if_owned(repo, branch, branch_tip):
                print(f"warning: preserved branch {branch}; it no longer matches this transaction's tip", file=sys.stderr)


def open_pr(path: Path, yes: bool):
    """Validate, isolate, commit, push, and verify one knowledge contribution."""
    root = local_root()
    if not root:
        die("run this inside a clone of the repo (or your fork)")
    root = root.resolve()
    repo = root.parent.resolve()
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        die(f"note must be inside {root}: {path}")
    if path.is_symlink() or not path.is_file():
        die(f"note must be a regular file: {path}")

    meta, _ = parse(path)
    fails, _ = check_note(path, root)
    if fails:
        die("fix these first:\n  " + "\n  ".join(fails))
    branch = f"kb/{slug(meta.get('game', '') or 'technique')}-{slug(meta.get('title', 'note'))}"[:80]
    title = f"kb: {meta.get('title')}" + (f" ({meta.get('game')})" if meta.get("game") else "")
    body = (f"Field note: **{meta.get('title')}**\n\n- game: {meta.get('game', '-')}\n- engine / route: {meta.get('engine', '-')} / "
            f"{meta.get('route', '-')}\n- status: {meta.get('status')}\n- agents: {', '.join(meta.get('agents') or [])}\n\n"
            "Checked with `um kb check`; index regenerated with `um kb index`.\n\n"
            "- [x] no game files, decompiled code dumps or secrets\n- [x] versions and verification written down\n")
    note_text = path.read_text(encoding="utf-8")
    media_root = path.parent / "media"
    media_refs = sorted(set(re.findall(r"(?<![A-Za-z0-9_.-])(media/[A-Za-z0-9_./-]+)", note_text)))
    media = []
    for ref in media_refs:
        candidate = (path.parent / PurePosixPath(ref)).resolve()
        try:
            candidate.relative_to(media_root.resolve())
        except ValueError:
            die(f"media reference escapes the note media directory: {ref}")
        if candidate.is_symlink() or not candidate.is_file():
            die(f"referenced PR media must be a regular file: {ref}")
        media.append(candidate)
    contribution = [path, *media]
    allowed = {str(p.relative_to(repo)) for p in contribution}
    note_rel = str(path.relative_to(repo))
    _validate_pr_worktree(repo, allowed)

    with tempfile.TemporaryDirectory(prefix="um-kb-publish-") as td:
        candidate = Path(td)
        (candidate / "README.md").write_text("Knowledge contribution publish preflight\n", encoding="utf-8")
        for source in [path, *media]:
            dest = candidate / source.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest, follow_symlinks=False)
        from um.publish import check as publish_check
        if publish_check(str(candidate)):
            die("knowledge contribution failed the publish safety check")

    can_push = False
    if shutil.which("gh"):
        r = subprocess.run(["gh", "api", f"repos/{REPO}", "--jq", ".permissions.push"], capture_output=True, text=True)
        can_push = r.stdout.strip() == "true"
    remote = "origin" if can_push else "fork"
    preview = [
        ["git", "checkout", "-b", branch],
        ["um", "kb", "index"],
        ["git", "add", "--", *[str(p) for p in contribution]],
        ["git", "commit", "-m", title],
    ]
    if not can_push:
        preview.append(["gh", "repo", "fork", "--remote", "--remote-name", "fork"])
    preview += [["git", "push", "-u", remote, branch],
                ["gh", "pr", "create", "--repo", REPO, "--head", branch, "--title", title, "--body", body]]
    if not yes:
        print("dry run (add --yes after your human agrees):")
        for command in preview:
            print("  " + " ".join(command if len(" ".join(command)) < 200 else command[:6] + ["..."]))
        return
    if not shutil.which("gh"):
        die("needs the GitHub CLI (gh) logged in; or push a branch and open the PR on github.com")

    _ensure_branch_absent(repo, branch)
    _validate_pr_worktree(repo, allowed)
    print(_publish_pr_isolated(repo, root, contribution, branch, title, body, can_push, note_rel))


# --------------------------------------------------------------------------- CLI

def main(a):
    c = a.cmd
    if c == "sync":
        sync()
        return
    if c == "search":
        root = resolve_root(a.root, a.remote)
        res = search(root, a.terms, a.game, a.engine, a.route, a.limit)
        if a.json:
            print(json.dumps(res, indent=1))
            return
        if not res:
            print(f"nothing in {root} matches; you may be first - write it up afterwards (`um kb new`)")
        for r in res:
            facts = " | ".join(str(x) for x in (r["game"], r["engine"], r["route"], r["status"]) if x) or "technique"
            print(f"{r['path']}\n   {r['title']}  [{facts}]")
            for h in r["hits"]:
                print(f"     | {h.lstrip('> ')[:160]}")
        return
    if c == "show":
        root = resolve_root(a.root, a.remote)
        p = root / a.note
        if not p.exists():
            cands = [x for x in root.rglob("*.md") if a.note in x.as_posix()]
            if not cands:
                die(f"no note {a.note!r} in {root}")
            p = cands[0]
        print(p.read_text(encoding="utf-8"))
        return
    if c == "new":
        root = Path(a.root) if a.root else local_root()
        if not root:
            die("run inside a clone of the repo (knowledge/ is written there), or pass --root")
        p = new_note(root, a.game, a.title, a.kind, a.from_scan, a.engine, a.route, a.agent, a.out)
        print(p)
        print("next: fill it in (Gotchas matter most), `um kb check " + str(p) + "`, `um kb index`, then a PR (`um kb pr ...`)")
        return
    if c == "check":
        root = Path(a.root) if a.root else local_root()
        paths = [Path(x) for x in a.paths] or ([p for p, _, _ in notes(root)] if root else [])
        bad = 0
        for p in paths:
            fails, warns = check_note(p, root)
            for f in fails:
                print(f"FAIL {p}: {f}")
            for w in warns:
                print(f"WARN {p}: {w}")
            bad += bool(fails)
        if root and a.index and not a.paths:
            idx, _ = build_index(root)
            if not (root / "INDEX.md").exists() or (root / "INDEX.md").read_text(encoding="utf-8") != idx:
                print("FAIL knowledge/INDEX.md is out of date: run `um kb index`")
                bad += 1
        print(f"{'FAIL' if bad else 'PASS'}: {len(paths)} notes checked")
        raise SystemExit(1 if bad else 0)
    if c == "index":
        root = Path(a.root) if a.root else local_root()
        if not root:
            die("no local knowledge/ folder")
        idx, rows = build_index(root)
        (root / "INDEX.md").write_text(idx, **TEXT)
        (root / "index.json").write_text(json.dumps(rows, indent=1, default=str) + "\n", **TEXT)
        print(f"{root / 'INDEX.md'}: {len(rows)} notes")
        return
    if c == "pr":
        open_pr(Path(a.note), a.yes)


def register(sub):
    import argparse
    p = sub.add_parser("kb", help="knowledge base of how games were modded: search, write, check, PR",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")
    q = cs.add_parser("search", help="find prior notes (local clone, else the GitHub copy)")
    q.add_argument("terms", nargs="*")
    q.add_argument("--game")
    q.add_argument("--engine")
    q.add_argument("--route", choices=ROUTES)
    q.add_argument("--limit", type=int, default=10)
    q.add_argument("--json", action="store_true")
    q.add_argument("--remote", action="store_true", help="search the synced GitHub copy even inside a clone")
    q.add_argument("--root")
    q.set_defaults(func=main)
    q = cs.add_parser("show", help="print a note")
    q.add_argument("note")
    q.add_argument("--remote", action="store_true")
    q.add_argument("--root")
    q.set_defaults(func=main)
    q = cs.add_parser("new", help="scaffold a note from the template")
    q.add_argument("--title", required=True)
    q.add_argument("--game")
    q.add_argument("--kind", default="game", choices=["game", "technique"])
    q.add_argument("--from-scan", help="pre-fill engine / anti-cheat / loaders from `um scan <game>`")
    q.add_argument("--engine")
    q.add_argument("--route", choices=ROUTES)
    q.add_argument("--agent", help='e.g. "Codex (gpt-6)"; default $UM_AGENT')
    q.add_argument("--out")
    q.add_argument("--root")
    q.set_defaults(func=main)
    q = cs.add_parser("check", help="validate notes (all, or the given paths)")
    q.add_argument("paths", nargs="*")
    q.add_argument("--index", action="store_true", help="also fail if INDEX.md is stale")
    q.add_argument("--root")
    q.set_defaults(func=main)
    q = cs.add_parser("index", help="regenerate knowledge/INDEX.md and index.json")
    q.add_argument("--root")
    q.set_defaults(func=main)
    cs.add_parser("sync", help="refresh the cached GitHub copy").set_defaults(func=main)
    q = cs.add_parser("pr", help="open a pull request with a note (dry run unless --yes)")
    q.add_argument("note")
    q.add_argument("--yes", action="store_true", help="really branch, push and open the PR")
    q.set_defaults(func=main)
