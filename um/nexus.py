"""Nexus Mods from the command line: search (public, no key), mod and file details, downloads with your own
API key, and the nxm:// handler that makes the site's "Mod manager download" button land in `um`.

    um nexus key set|status|clear            # your personal key: nexusmods.com > Settings > API keys
    um nexus validate                        # who the key belongs to, premium or not, requests left today
    um nexus search "4k texture" [--game cyberpunk2077] [--sort endorsements|downloads|updated]
                                  [--count 20] [--offset 0] [--adult] [--json]
    um nexus mod 1234                        # one mod: version, author, category, endorsements, summary
    um nexus files 1234                      # its downloadable files: id, category, version, size, date
    um nexus download 1234 [--file ID] [--out DIR]
    um nexus nxm "nxm://cyberpunk2077/mods/1234/files/5678?key=...&expires=..." [--install]
    um nexus nxm-register [--no-install]     # Windows: send nxm:// links to `um nexus nxm` (writes HKCU)

The key comes from NEXUS_API_KEY, else from ~/.secrets/nexus-key (`um nexus key set` prompts for it; it never
goes on a command line). Search needs no key. Downloads need one: Premium accounts get direct links from the
API; free accounts click "Mod manager download" on the site, which hands `um nexus nxm` a one-time link.
Nexus allows 2,500 requests a day (then 100 an hour) and forbids bulk scraping: one page at a time.
Every download gets a sidecar `<file>.nexus.json` (mod, file, version) that `um cp77 install` records.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from um import __version__
from um.common import data_dir, die, emit, is_windows, text_console
from um.fal import file_mode, mask, write_key_file

API = "https://api.nexusmods.com"
APP_NAME = "universal-modder"
DEFAULT_GAME = "cyberpunk2077"
KEY_FILE = Path("~/.secrets/nexus-key")
LAST_LIMITS: dict = {}
SORTS = {"endorsements": "endorsements", "downloads": "downloads", "updated": "updatedAt", "created": "createdAt"}
CATEGORY_ORDER = ["MAIN", "UPDATE", "OPTIONAL", "MISCELLANEOUS", "OLD_VERSION", "ARCHIVED"]


class NexusError(Exception):
    pass


# --------------------------------------------------------------------------- key

def key_file() -> Path:
    return Path(os.environ.get("UM_NEXUS_KEY_FILE") or KEY_FILE).expanduser()


def key_sources() -> list[tuple[str, str]]:
    out = []
    env = (os.environ.get("NEXUS_API_KEY") or "").strip()
    if env:
        out.append(("NEXUS_API_KEY environment variable", env))
    try:
        k = key_file().read_text().strip()
        if k:
            out.append((f"key file {key_file()} (mode {file_mode(key_file())})", k))
    except OSError:
        pass
    return out


def nexus_key(required: bool = True) -> str | None:
    s = key_sources()
    if s:
        return s[0][1]
    if required:
        die("no Nexus API key. Create a personal key at https://www.nexusmods.com/users/myaccount?tab=api+access, "
            "then `um nexus key set` (or set NEXUS_API_KEY)")
    return None


def cmd_key(args):
    kf = key_file()
    if args.action == "set":
        value = Path(args.from_file).expanduser().read_text().strip() if args.from_file else getpass.getpass("Nexus API key (hidden): ").strip()
        if not value:
            die("empty key, nothing stored")
        print(f"stored {mask(value)} in {write_key_file(value, kf)} (plaintext, owner-only)")
        if os.environ.get("NEXUS_API_KEY"):
            print("note: NEXUS_API_KEY is set in this environment and takes precedence over the stored key")
    elif args.action == "status":
        s = key_sources()
        if not s:
            print("no Nexus key configured; run `um nexus key set`")
        for i, (label, key) in enumerate(s):
            print(f"{'active  ' if i == 0 else 'shadowed'}  {label}  ->  {mask(key)}")
    elif args.action == "clear":
        if kf.exists():
            kf.unlink()
            print(f"removed {kf}")
        else:
            print("nothing to remove")


# --------------------------------------------------------------------------- HTTP

def _request(method: str, url: str, key: str | None = None, data=None, params: dict | None = None, timeout: int = 60):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    headers = {"User-Agent": f"{APP_NAME}/{__version__}", "Accept": "application/json",
               "Application-Name": APP_NAME, "Application-Version": __version__}
    if key:
        headers["apikey"] = key
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.load(r)
            for h in ("x-rl-daily-remaining", "x-rl-daily-reset", "x-rl-hourly-remaining", "x-rl-hourly-reset"):
                if r.headers.get(h):
                    LAST_LIMITS[h[5:]] = r.headers[h]
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")[:600]
        try:
            msg = json.loads(text).get("message") or text
        except ValueError:
            msg = text
        if e.code == 401:
            raise NexusError(f"Nexus rejected the API key (401): {msg}")
        if e.code == 403:
            raise NexusError(f"forbidden (403): {msg}\nDirect download links need Nexus Premium; on a free account use the "
                             "site's \"Mod manager download\" button and `um nexus nxm <link>`")
        if e.code == 429:
            raise NexusError("rate limited (429): Nexus allows 2,500 requests a day, then 100 an hour; wait and retry")
        if e.code == 404:
            raise NexusError(f"not found (404): {url}")
        raise NexusError(f"HTTP {e.code} for {url}: {msg}")
    except urllib.error.URLError as e:
        raise NexusError(f"cannot reach Nexus: {e.reason}")
    return payload


def get(path: str, key: str | None = None, params: dict | None = None):
    return _request("GET", API + path, key=key, params=params)


def graphql(query: str, variables: dict):
    r = _request("POST", API + "/v2/graphql", data={"query": query, "variables": variables})
    if r.get("errors"):
        raise NexusError("GraphQL: " + "; ".join(e.get("message", "?") for e in r["errors"]))
    return r["data"]


# --------------------------------------------------------------------------- API calls

SEARCH_QUERY = """query($f: ModsFilter, $s: [ModsSort!], $c: Int, $o: Int) {
  mods(filter: $f, sort: $s, count: $c, offset: $o) { totalCount nodes {
    modId name summary version endorsements downloads updatedAt adultContent author
    uploader { name } modCategory { name } game { domainName } pictureUrl } } }"""


def search(text: str, game: str = DEFAULT_GAME, sort: str = "endorsements", count: int = 20, offset: int = 0,
           adult: bool | None = False) -> dict:
    """Public search (no key). `sort` is a SORTS key. adult=None lists adult mods too."""
    f: dict = {"gameDomainName": {"value": game, "op": "EQUALS"}}
    if text:
        f["name"] = {"value": text, "op": "WILDCARD"}
    if adult is not None:
        f["adultContent"] = {"value": adult, "op": "EQUALS"}
    s = [{SORTS.get(sort, sort): {"direction": "DESC"}}]
    return graphql(SEARCH_QUERY, {"f": f, "s": s, "c": min(max(count, 1), 50), "o": max(offset, 0)})["mods"]


def validate(key: str) -> dict:
    return get("/v1/users/validate.json", key)


def mod_info(game: str, mod_id: int, key: str) -> dict:
    return get(f"/v1/games/{game}/mods/{mod_id}.json", key)


def _cat_rank(f: dict) -> int:
    c = f.get("category_name") or "ARCHIVED"
    return CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 9


def mod_files(game: str, mod_id: int, key: str) -> list[dict]:
    r = get(f"/v1/games/{game}/mods/{mod_id}/files.json", key)
    files = r.get("files", [])
    files.sort(key=lambda f: (_cat_rank(f), -(f.get("uploaded_timestamp") or 0)))
    return files


def download_links(game: str, mod_id: int, file_id: int, key: str, nxm_key: str | None = None, expires: str | None = None) -> list[dict]:
    params = {"key": nxm_key, "expires": expires} if nxm_key else None
    return get(f"/v1/games/{game}/mods/{mod_id}/files/{file_id}/download_link.json", key, params)


def pick_file(files: list[dict], file_id: int | None = None) -> dict:
    """The file to install: the requested id, else the primary main file, else the single main file."""
    if file_id is not None:
        for f in files:
            if f.get("file_id") == file_id:
                return f
        raise NexusError(f"no file {file_id} on this mod; `um nexus files` lists them")
    mains = [f for f in files if (f.get("category_name") or "") == "MAIN"]
    primary = [f for f in mains if f.get("is_primary")]
    if len(primary) == 1:
        return primary[0]
    if len(mains) == 1:
        return mains[0]
    if not mains:
        raise NexusError("this mod has no main file; pick one with --file ID (`um nexus files` lists them)")
    lines = "\n".join(f"  --file {f['file_id']:<8} {f.get('name')}  v{f.get('version')}  {size_str(f)}" for f in mains)
    raise NexusError(f"this mod has {len(mains)} main files (variants); pick one:\n{lines}")


def size_str(f: dict) -> str:
    b = f.get("size_in_bytes") or (f.get("size_kb") or 0) * 1024
    return f"{b / 2**20:.1f} MB" if b >= 2**20 else f"{b / 1024:.0f} KB"


def parse_nxm(url: str) -> dict:
    """nxm://<game>/mods/<mod>/files/<file>?key=...&expires=...&user_id=..."""
    u = urllib.parse.urlparse(url.strip())
    m = re.fullmatch(r"/mods/(\d+)/files/(\d+)/?", u.path)
    if u.scheme != "nxm" or not u.netloc or not m:
        raise NexusError(f"not an nxm:// mod file link: {url!r}")
    q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
    return dict(game=u.netloc, mod_id=int(m.group(1)), file_id=int(m.group(2)), key=q.get("key"),
                expires=q.get("expires"), user_id=q.get("user_id"))


def download_dir(game: str) -> Path:
    d = data_dir() / "nexus" / "downloads" / game
    d.mkdir(parents=True, exist_ok=True)
    return d


def download(url: str, dest: Path, expected: int | None = None, quiet: bool = False) -> Path:
    """Stream to dest.part, check the size when Nexus told us one, then rename."""
    part = dest.with_name(dest.name + ".part")
    url = urllib.parse.quote(url, safe="/:?=&%+~@!$'()*,;")  # CDN links carry the file name, spaces included
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{__version__}"})
    done, t0, last = 0, time.time(), 0.0
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(part, "wb") as f:
            total = expected or int(r.headers.get("Content-Length") or 0)
            for chunk in iter(lambda: r.read(1 << 20), b""):
                f.write(chunk)
                done += len(chunk)
                if not quiet and time.time() - last > 0.5:
                    last = time.time()
                    pct = f" {100 * done / total:3.0f}%" if total else ""
                    print(f"\r  {dest.name}: {done / 2**20:.1f} MB{pct}", end="", file=sys.stderr, flush=True)
    except urllib.error.URLError as e:
        part.unlink(missing_ok=True)
        raise NexusError(f"download failed: {e.reason}")
    if not quiet:
        print(f"\r  {dest.name}: {done / 2**20:.1f} MB in {time.time() - t0:.0f}s", file=sys.stderr)
    if expected and abs(done - expected) > 1024:
        part.unlink(missing_ok=True)
        raise NexusError(f"size mismatch: got {done} bytes, Nexus said {expected}")
    part.replace(dest)
    return dest


def sidecar(path: Path) -> Path:
    return path.with_name(path.name + ".nexus.json")


def fetch_file(game: str, mod_id: int, file_id: int | None, key: str, out: Path | None = None,
               nxm: dict | None = None, quiet: bool = False) -> tuple[Path, dict]:
    """Download one mod file (by id, or the main file) and write its sidecar. Returns (path, meta)."""
    info = mod_info(game, mod_id, key)
    files = mod_files(game, mod_id, key)
    f = pick_file(files, file_id)
    out = out or download_dir(game)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / (f.get("file_name") or f"{mod_id}-{f['file_id']}.zip")
    meta = dict(game=game, mod_id=mod_id, mod_name=info.get("name"), mod_version=info.get("version"),
                author=info.get("author"), file_id=f["file_id"], file_name=f.get("file_name"),
                file_label=f.get("name"), file_version=f.get("version"), category=f.get("category_name"),
                uploaded=f.get("uploaded_timestamp"), size=f.get("size_in_bytes"),
                url=f"https://www.nexusmods.com/{game}/mods/{mod_id}?tab=files")
    if dest.exists() and f.get("size_in_bytes") and dest.stat().st_size == f["size_in_bytes"]:
        if not quiet:
            print(f"  already downloaded: {dest}", file=sys.stderr)
    else:
        links = download_links(game, mod_id, f["file_id"], key, nxm.get("key") if nxm else None, nxm.get("expires") if nxm else None)
        if not links:
            raise NexusError("Nexus returned no download link")
        download(links[0]["URI"], dest, f.get("size_in_bytes"), quiet=quiet)
    meta["downloaded_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    meta["path"] = str(dest)
    sidecar(dest).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return dest, meta


# --------------------------------------------------------------------------- commands

def _run(fn, args):
    try:
        return fn(args)
    except NexusError as e:
        die(str(e))


def _limits_line() -> str:
    if not LAST_LIMITS:
        return ""
    return f"requests left: {LAST_LIMITS.get('daily-remaining', '?')} today, {LAST_LIMITS.get('hourly-remaining', '?')} this hour"


def cmd_validate(args):
    u = validate(nexus_key())
    print(f"user      {u.get('name')} (id {u.get('user_id')})")
    print(f"premium   {'yes: direct download links' if u.get('is_premium') else 'no: use the site button + um nexus nxm'}")
    print(f"supporter {'yes' if u.get('is_supporter') else 'no'}")
    print(_limits_line())


def cmd_search(args):
    r = search(args.text, args.game, args.sort, args.count, args.offset, None if args.adult else False)
    if args.json:
        emit(r, True)
        return
    print(f"{r['totalCount']} mods match {args.text!r} on {args.game} (showing {len(r['nodes'])}, sorted by {args.sort})")
    for n in r["nodes"]:
        flag = " [adult]" if n.get("adultContent") else ""
        print(f"\n{n['modId']:>6}  {n['name']}{flag}  v{n.get('version')}  by {n.get('author')}  [{(n.get('modCategory') or {}).get('name')}]")
        print(f"        {n.get('endorsements') or 0:,} endorsements, {n.get('downloads') or 0:,} downloads, updated {str(n.get('updatedAt'))[:10]}")
        if n.get("summary"):
            print(f"        {n['summary'][:160]}")


def cmd_mod(args):
    m = mod_info(args.game, args.mod_id, nexus_key())
    if args.json:
        emit(m, True)
        return
    print(f"{m.get('name')}  v{m.get('version')}  by {m.get('author')} (uploaded by {m.get('uploaded_by')})")
    print(f"  {m.get('endorsement_count') or 0:,} endorsements, {m.get('mod_downloads') or 0:,} downloads, "
          f"updated {time.strftime('%Y-%m-%d', time.gmtime(m.get('updated_timestamp') or 0))}"
          f"{', adult' if m.get('contains_adult_content') else ''}{'' if m.get('available', True) else ', NOT AVAILABLE'}")
    print(f"  https://www.nexusmods.com/{args.game}/mods/{args.mod_id}")
    if m.get("summary"):
        print(f"  {m['summary']}")
    print(_limits_line())


def cmd_files(args):
    files = mod_files(args.game, args.mod_id, nexus_key())
    if args.json:
        emit(files, True)
        return
    for f in files:
        if f.get("category_name") in ("OLD_VERSION", "ARCHIVED") and not args.all:
            continue
        star = "*" if f.get("is_primary") else " "
        print(f"{f['file_id']:>8} {star} {f.get('category_name') or '':<13} v{str(f.get('version')):<10} {size_str(f):>9}  "
              f"{time.strftime('%Y-%m-%d', time.gmtime(f.get('uploaded_timestamp') or 0))}  {f.get('name')}")
        if f.get("description") and args.verbose:
            print("           " + re.sub(r"\[/?[^\]]+\]", "", f["description"]).strip().replace("\n", "\n           ")[:400])
    print("\n* = the file Nexus marks primary; `um nexus download MOD --file ID` picks another. "
          "--all shows old versions.")


def cmd_download(args):
    out = Path(args.out).expanduser() if args.out else None
    path, meta = fetch_file(args.game, args.mod_id, args.file, nexus_key(), out)
    print(f"{path}\n  {meta['mod_name']} - {meta['file_label']} v{meta['file_version']} ({meta['category']})")
    print(_limits_line())


def cmd_nxm(args):
    link = parse_nxm(args.url)
    out = Path(args.out).expanduser() if args.out else None
    try:
        path, meta = fetch_file(link["game"], link["mod_id"], link["file_id"], nexus_key(), out, nxm=link)
        print(f"{path}\n  {meta['mod_name']} - {meta['file_label']} v{meta['file_version']}")
        if args.install:
            if link["game"] != "cyberpunk2077":
                print(f"not installing: `um cp77` manages Cyberpunk 2077 only, this link is for {link['game']}")
            else:
                from um import cp77
                cp77.install_paths([path])
    finally:
        if args.pause:
            input("\nPress Enter to close")


def _um_cmd() -> Path:
    return Path(__file__).resolve().parents[1] / "bin" / "um.cmd"


def cmd_nxm_register(args):
    if not is_windows():
        die("the nxm:// handler registration is Windows-only here; on Linux add a .desktop entry with "
            "`MimeType=x-scheme-handler/nxm` whose Exec runs `um nexus nxm %u`")
    um = _um_cmd()
    if not um.exists():
        die(f"bin/um.cmd not found at {um}")
    cmdline = f'"{um}" nexus nxm "%1"' + ("" if args.no_install else " --install") + " --pause"
    steps = [["reg", "add", r"HKCU\Software\Classes\nxm", "/ve", "/d", "URL:Nexus Mods Protocol", "/f"],
             ["reg", "add", r"HKCU\Software\Classes\nxm", "/v", "URL Protocol", "/d", "", "/f"],
             ["reg", "add", r"HKCU\Software\Classes\nxm\shell\open\command", "/ve", "/d", cmdline, "/f"]]
    if args.remove:
        steps = [["reg", "delete", r"HKCU\Software\Classes\nxm", "/f"]]
    print("This writes the current user's registry (HKCU\\Software\\Classes\\nxm) so that nxm:// links run:")
    print(f"  {cmdline}" if not args.remove else "  (removing the handler)")
    if not args.yes:
        if input("Proceed? [y/N] ").strip().lower() not in ("y", "yes"):
            die("cancelled")
    for s in steps:
        r = subprocess.run(s, capture_output=True, **text_console())
        if r.returncode:
            die(f"{' '.join(s[:3])} failed: {(r.stderr or r.stdout).strip()}")
    print("done. On the Nexus site, pick Vortex/'Mod manager download'; Windows will offer `um` for nxm:// links."
          if not args.remove else "handler removed")


def register(sub):
    p = sub.add_parser("nexus", help="Nexus Mods: search, files, downloads with your API key, nxm:// handler",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", metavar="<cmd>")

    k = s.add_parser("key", help="set / status / clear the API key")
    k.add_argument("action", choices=["set", "status", "clear"])
    k.add_argument("--from-file", help="read the key from this file instead of prompting")
    k.set_defaults(func=cmd_key)

    v = s.add_parser("validate", help="check the key: user, premium, rate limit")
    v.set_defaults(func=lambda a: _run(cmd_validate, a))

    q = s.add_parser("search", help="search mods (public, no key)")
    q.add_argument("text", nargs="?", default="", help="words in the mod name; empty lists the top mods")
    q.add_argument("--game", default=DEFAULT_GAME, help="Nexus game domain, e.g. cyberpunk2077, skyrimspecialedition")
    q.add_argument("--sort", default="endorsements", choices=list(SORTS))
    q.add_argument("--count", type=int, default=20)
    q.add_argument("--offset", type=int, default=0)
    q.add_argument("--adult", action="store_true", help="include adult-flagged mods")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=lambda a: _run(cmd_search, a))

    for name, fn, hlp in (("mod", cmd_mod, "one mod's details"), ("files", cmd_files, "a mod's downloadable files")):
        m = s.add_parser(name, help=hlp)
        m.add_argument("mod_id", type=int)
        m.add_argument("--game", default=DEFAULT_GAME)
        m.add_argument("--json", action="store_true")
        if name == "files":
            m.add_argument("--all", action="store_true", help="include old versions")
            m.add_argument("-v", "--verbose", action="store_true", help="show file descriptions")
        m.set_defaults(func=lambda a, fn=fn: _run(fn, a))

    d = s.add_parser("download", help="download a mod file (Premium: direct)")
    d.add_argument("mod_id", type=int)
    d.add_argument("--file", type=int, help="file id (default: the primary main file)")
    d.add_argument("--game", default=DEFAULT_GAME)
    d.add_argument("--out", help="folder (default ~/.universal-modder/nexus/downloads/<game>)")
    d.set_defaults(func=lambda a: _run(cmd_download, a))

    n = s.add_parser("nxm", help="download an nxm:// link from the site's Mod manager download button")
    n.add_argument("url")
    n.add_argument("--out")
    n.add_argument("--install", action="store_true", help="then `um cp77 install` it (Cyberpunk 2077 links)")
    n.add_argument("--pause", action="store_true", help="wait for Enter before exiting (for the protocol handler window)")
    n.set_defaults(func=lambda a: _run(cmd_nxm, a))

    r = s.add_parser("nxm-register", help="Windows: register `um` as the nxm:// handler (asks first)")
    r.add_argument("--no-install", action="store_true", help="download only, don't install into Cyberpunk")
    r.add_argument("--remove", action="store_true", help="remove the handler instead")
    r.add_argument("--yes", action="store_true")
    r.set_defaults(func=cmd_nxm_register)
