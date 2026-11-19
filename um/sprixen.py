"""2D game sprites from Sprixen (https://sprixen.com): one style per project, animation sheets, terrain tiles.

    um sprixen key set                                       # hidden prompt; or set SPRIXEN_API_KEY
    um sprixen credits                                       # plan and credits left
    um sprixen sprite "a rusty scrap drone enemy, side view facing left" --name drone
    um sprixen sprite "a red health potion" --style pixel_art --size 32x32 --view side_scroll --variants 3
    um sprixen animate <sprite_id> --type walk --frames 8 --name drone_walk   # keeps the sprite's facing
    um sprixen animate <sprite_id> --type attack --weapon-type sword --weapon-hand right
    um sprixen tile "mossy cobblestone floor" --projection top_down --name floor   # then: um sprite tile-preview
    um sprixen projects                                      # style projects and their sprite counts

Style lives in a Sprixen project (art style, resolution, view angle, palette), so every sprite generated in
the same project shares one look. `sprite` reuses the project named by --project, or one named after the
style flags ("um pixel_art side_scroll"), and creates it on first use. Sprites come back on a transparent
background and print their sprite id: pass it to `animate`, which returns one horizontal strip of frames
(frame size = sheet width / frames x sheet height; `um sprite slice` splits it, `um sprite sheet --vertical`
restacks it for Terraria-style NPCs).

Sprixen is a paid service: it needs an account, an API key (https://sprixen.com/settings/api) and credits
(sprite 2 per variant, animation 4, premium 8, tile 1); `um sprixen credits` shows what is left. The key is
read from SPRIXEN_API_KEY, else from where `um sprixen key set` stored it (the desktop keyring on Linux, an
owner-only ~/.secrets/sprixen-key elsewhere), else from SPRIXEN_API_KEY=... in a .env.
Files land in --out (default assets/gen), and each call appends a line to <out>/sprixen_manifest.jsonl (ids,
prompt, settings, files) so an asset can be traced.
"""
from __future__ import annotations

import getpass
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from um.common import die

DEFAULT_URL = "https://api.sprixen.com"
STYLES = ["pixel_art", "cartoon", "anime", "hand_drawn", "chibi"]
VIEWS = ["side_scroll", "top_down", "isometric", "front_facing"]
SIZES = ["16x16", "32x32", "64x64", "128x128", "256x256", "512x512"]
ANIMATIONS = ["idle", "walk", "run", "attack", "jump", "death", "hurt", "custom"]
DIRECTIONS = ["right", "left", "up", "down", "up-right", "up-left", "down-right", "down-left"]
_DEFAULT_KEY_FILE = "~/.secrets/sprixen-key"
KEYRING_ATTRS = ["service", "sprixen.com", "key", "api"]
_KEY_CACHE: str | None = None


# --------------------------------------------------------------------------- key


def key_file() -> Path:
    return Path(os.environ.get("UM_SPRIXEN_KEY_FILE") or _DEFAULT_KEY_FILE).expanduser()


def _read_dotenv(p: Path) -> str | None:
    try:
        m = re.search(r"^\s*SPRIXEN_API_KEY\s*=\s*['\"]?([^'\"\s]+)", p.read_text(), re.M)
    except OSError:
        return None
    return m.group(1) if m else None


def keyring_available() -> bool:
    from um.fal import keyring_available
    return keyring_available()


def keyring_get() -> str | None:
    """The key in the desktop keyring (libsecret's secret-tool, the same route as `um fal key`), or None."""
    from um.fal import _secret_tool
    r = _secret_tool("lookup", *KEYRING_ATTRS)
    return (r.stdout.strip() or None) if r and r.returncode == 0 else None


def keyring_set(value: str) -> bool:
    from um.fal import _secret_tool
    r = _secret_tool("store", "--label", "Sprixen API key (universal-modder)", *KEYRING_ATTRS, value=value)
    return bool(r and r.returncode == 0)


def keyring_clear() -> bool:
    from um.fal import _secret_tool
    r = _secret_tool("clear", *KEYRING_ATTRS)
    return bool(r and r.returncode == 0)


def _key_candidates():
    """(label, reader) in precedence order. Nothing is read until its reader is called, so a SPRIXEN_API_KEY in
    the environment never touches the keyring."""
    from um.fal import _read_file
    named, kf = os.environ.get("UM_SPRIXEN_KEY_FILE"), key_file()
    yield "SPRIXEN_API_KEY environment variable", lambda: (os.environ.get("SPRIXEN_API_KEY") or "").strip() or None
    if named:                                                 # a file named on purpose comes before the keyring
        yield f"key file {kf} (UM_SPRIXEN_KEY_FILE)", lambda: _read_file(kf)
    yield f"OS keyring ({' '.join(KEYRING_ATTRS)})", keyring_get
    if not named:
        yield f"key file {kf}", lambda: _read_file(kf)
    for p in dict.fromkeys((Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env")):
        yield f".env {p}", lambda p=p: _read_dotenv(p)


def key_sources() -> list[tuple[str, str]]:
    """(label, key) for every source that has a key, in precedence order: the first one is used."""
    return [(label, k) for label, read in _key_candidates() if (k := read())]


def api_key() -> str:
    """The first key found, read once per run (a poll loop would otherwise ask the keyring every few seconds)."""
    global _KEY_CACHE
    if not _KEY_CACHE:
        _KEY_CACHE = next((k for _, read in _key_candidates() if (k := read())), None)
    if not _KEY_CACHE:
        die("no Sprixen key. Create one at https://sprixen.com/settings/api, then `um sprixen key set` "
            "(or set SPRIXEN_API_KEY)")
    return _KEY_CACHE


def cmd_key(a):
    from um.fal import file_mode, mask, write_key_file
    if a.action == "set":
        value = Path(a.from_file).expanduser().read_text().strip() if a.from_file else getpass.getpass("Sprixen API key (hidden): ").strip()
        if not value:
            die("empty key, nothing stored")
        if not value.startswith("spx_"):
            print("note: Sprixen keys start with spx_live_; storing it anyway", file=sys.stderr)
        if getattr(a, "file_only", False):
            print(f"stored in {write_key_file(value, key_file())} as {mask(value)} (plaintext, owner-only)")
        elif keyring_set(value) and keyring_get() == value:
            print(f"stored in the OS keyring as {mask(value)} ({' '.join(KEYRING_ATTRS)})")
        elif keyring_available():
            die("could not write to the OS keyring (is it unlocked?); "
                "`um sprixen key set --file-only` stores the key in a plaintext file instead")
        else:
            print(f"no OS keyring (no secret-tool); stored in {write_key_file(value, key_file())} as {mask(value)} "
                  "(plaintext, owner-only)")
        if os.environ.get("SPRIXEN_API_KEY"):
            print("note: SPRIXEN_API_KEY is set in this environment and takes precedence over the stored key")
    elif a.action == "clear":
        removed = []
        if keyring_get() and keyring_clear():
            removed.append("OS keyring")
        kf = key_file()
        if kf.exists():
            kf.unlink()
            removed.append(str(kf))
        print("removed: " + ", ".join(removed) if removed else "nothing to remove")
    else:
        sources = key_sources()
        if not sources:
            print("no Sprixen key configured; run `um sprixen key set`")
        for i, (label, k) in enumerate(sources):
            print(f"{'active  ' if i == 0 else 'shadowed'}  {label}  ->  {mask(k)}")
        kf = key_file()
        print(f"keyring     {'available' if keyring_available() else 'not available (no secret-tool)'}")
        print(f"key file    {kf} {'exists (mode ' + file_mode(kf) + ')' if kf.exists() else 'absent'}")


# --------------------------------------------------------------------------- http


def base_url(url: str | None = None) -> str:
    return (url or os.environ.get("SPRIXEN_API_URL") or DEFAULT_URL).rstrip("/")


def _error(code: int, body: bytes) -> tuple[str, dict]:
    """Sprixen errors are {statusCode, message, code?, hint?: {action, url?, details?}}: one readable line."""
    try:
        err = json.loads(body)
    except ValueError:
        return f"HTTP {code}: {body[:500].decode(errors='replace')}", {}
    msg = err.get("message")
    msg = "; ".join(map(str, msg)) if isinstance(msg, list) else str(msg or err.get("error") or "")
    hint = err.get("hint") or {}
    line = f"HTTP {code}{' ' + err['code'] if err.get('code') else ''}: {msg}"
    if hint.get("action"):
        line += f" (next: {hint['action']}{' ' + hint['url'] if hint.get('url') else ''})"
    return line, err


def request(base: str, method: str, path: str, body: dict | None = None, retries: int = 3):
    """JSON call to /v1<path> with the API key. Waits out 429 (rate limit) and 409 ACTIVE_GENERATION_LIMIT."""
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries + 1):
        req = urllib.request.Request(f"{base}/v1{path}", data=data, method=method, headers={
            "Authorization": f"Bearer {api_key()}", "Accept": "application/json",
            "User-Agent": "universal-modder", **({"Content-Type": "application/json"} if data is not None else {})})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                payload = r.read()
            return json.loads(payload) if payload else {}
        except ValueError:
            die(f"Sprixen {method} {path} answered with something that isn't JSON")
        except urllib.error.HTTPError as e:
            line, err = _error(e.code, e.read())
            wait = ((err.get("hint") or {}).get("details") or {}).get("retryAfterSeconds")
            if attempt < retries and (e.code == 429 or err.get("code") == "ACTIVE_GENERATION_LIMIT"):
                wait = float(wait or 15)
                print(f"um: {line}; retrying in {wait:.0f} s", file=sys.stderr)
                time.sleep(wait)
                continue
            die(f"Sprixen {method} {path} -> {line}")
        except urllib.error.URLError as e:
            die(f"no Sprixen API at {base} ({e.reason})")
        except OSError as e:                                  # a timeout or reset while reading the answer
            die(f"Sprixen {method} {path} failed: {e or type(e).__name__}")


def download(base: str, url: str, path: Path) -> Path:
    """Result URLs are relative (/api/public/uploads/...) or absolute; static files need no auth."""
    full = url if url.startswith("http") else base + url
    req = urllib.request.Request(full, headers={"User-Agent": "universal-modder"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            path.write_bytes(r.read())
    except OSError as e:                                      # URLError, HTTPError, or a timeout while reading
        die(f"could not download {full}: {getattr(e, 'reason', None) or e or type(e).__name__}")
    return path


def png_size(path: Path) -> tuple[int, int] | None:
    head = path.read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def wait(base: str, path: str, timeout: float, poll: float = 4.0) -> dict:
    """Poll a generation or animation until completed (returned) or failed (dies)."""
    end = time.time() + timeout
    last = None
    while time.time() < end:
        job = request(base, "GET", path)
        status = job.get("status")
        if status == "completed":
            return job
        if status == "failed":
            die(f"Sprixen job {job.get('id')} failed: {job.get('error') or 'no reason given'}")
        prog = job.get("progress") or {}
        note = f"{status} {prog.get('phase', '')} {prog.get('completed', '')}/{prog.get('total', '')}".strip(" /")
        if note != last:
            print(f"um: {path.rsplit('/', 2)[-2][:-1]} {job.get('id')}: {note}", file=sys.stderr)
            last = note
        time.sleep(poll)
    die(f"Sprixen didn't finish in {timeout:.0f} s ({path}). It was charged when it started and may still "
        "complete: check it at https://sprixen.com before running it again")


def record(out: Path, rec: dict):
    with open(out / "sprixen_manifest.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(t=time.strftime("%Y-%m-%dT%H:%M:%S"), **rec)) + "\n")


def _name(name: str | None, fallback: str) -> str:
    return name or "_".join(re.sub(r"[^a-z0-9 ]", "", fallback.lower()).split()[:5]) or "sprite"


# --------------------------------------------------------------------------- projects


def project_for(base: str, ref: str | None, style: str, view: str, size: str | None, palette: str | None) -> dict:
    """The project named (or with the id) ref, else the one named after the style; created on first use."""
    name = ref or f"um {style} {view}"
    for p in request(base, "GET", "/projects"):
        if ref and p.get("id") == ref or p.get("name") == name:
            if (p.get("artStyle"), p.get("viewAngle")) != (style, view) and not ref:
                print(f"um: project {name!r} keeps its own style ({p.get('artStyle')}, {p.get('viewAngle')})", file=sys.stderr)
            return p
    body = dict(name=name, artStyle=style, viewAngle=view, description="created by universal-modder")
    if size:
        body["resolution"] = size
    if palette:
        body["palette"] = [c.strip() for c in palette.split(",")] if "," in palette or palette.startswith("#") else palette
    p = request(base, "POST", "/projects", body)
    print(f"um: created Sprixen project {name!r} ({p.get('id')})", file=sys.stderr)
    return p


# --------------------------------------------------------------------------- commands


def cmd_sprite(a, base: str, out: Path):
    proj = project_for(base, a.project, a.style, a.view, a.size, a.palette)
    body = dict(prompt=a.prompt, projectId=proj["id"], variantCount=a.variants, pixelPerfect=a.pixel_perfect)
    if a.size:
        body["resolution"] = a.size
    if a.ref:
        body["referenceImageUrl"] = a.ref
    if a.no_base:
        body["noBase"] = True
    gen = request(base, "POST", "/generations", body)
    gen = wait(base, f"/generations/{gen['id']}", a.timeout)
    sprites = {s.get("imageUrl"): s for s in gen.get("sprites") or []}
    name = _name(a.name, a.prompt)
    files = []
    for i, url in enumerate(gen.get("resultUrls") or []):
        p = download(base, url, out / f"{name if i == 0 else f'{name}_{i + 1}'}.png")
        sid = sprites.get(url, {}).get("id")
        files.append(dict(file=str(p), sprite_id=sid, size=png_size(p)))
        print(p)
        if sid:
            print(f"  sprite id {sid}  (animate: um sprixen animate {sid} --type walk)")
    if not files:
        die(f"generation {gen['id']} completed with no images")
    record(out, dict(kind="sprite", generation_id=gen["id"], project=proj.get("name"), project_id=proj["id"],
                     prompt=a.prompt, style=proj.get("artStyle"), view=proj.get("viewAngle"), size=a.size,
                     credits=gen.get("creditsUsed"), files=files))


def cmd_animate(a, base: str, out: Path):
    body = dict(type=a.type, quality="premium" if a.premium else "standard")
    for k, v in (("direction", a.direction), ("frameCount", a.frames), ("fps", a.fps), ("customDescription", a.custom),
                 ("archetype", a.archetype), ("weaponHand", a.weapon_hand), ("weaponType", a.weapon_type),
                 ("resolution", a.size)):
        if v is not None:
            body[k] = v
    if a.shield:
        body["hasShield"] = True
    if a.type == "custom" and not a.custom:
        die("--type custom needs --custom \"what the character does\"")
    if not a.size:
        # frames default to the project's resolution; keep the size this sprite was generated at instead
        sp = request(base, "GET", f"/sprites/{a.sprite_id}")
        if sp.get("width") and sp.get("height"):
            body["resolution"] = f"{sp['width']}x{sp['height']}"
    anim = request(base, "POST", f"/sprites/{a.sprite_id}/animations", body)
    anim = wait(base, f"/animations/{anim['id']}", a.timeout)
    if not anim.get("spriteSheetUrl"):
        die(f"animation {anim['id']} completed with no sprite sheet")
    name = a.name or "_".join(x for x in (a.type, a.direction) if x)
    p = download(base, anim["spriteSheetUrl"], out / f"{name}.png")
    n = int(anim.get("frameCount") or 1)
    w, h = png_size(p) or (0, 0)
    fw = w // n if n else w
    print(p)
    print(f"  {n} frames of {fw}x{h} in one row at {anim.get('fps')} fps  (split: um sprite slice {p} <dir> --frame {fw}x{h})")
    record(out, dict(kind="animation", animation_id=anim["id"], sprite_id=a.sprite_id, type=a.type,
                     direction=a.direction, quality=body["quality"], frames=n, fps=anim.get("fps"),
                     frame_size=[fw, h], file=str(p)))


def cmd_tile(a, base: str, out: Path):
    body = dict(prompt=a.prompt, projectionType=a.projection, collision=a.collision, category=a.category)
    if a.flat:
        body["flatOnly"] = True
    gen = request(base, "POST", "/tile-packs/generate", body)
    gen = wait(base, f"/generations/{gen['id']}", a.timeout)
    urls = gen.get("resultUrls") or []
    if not urls:
        die(f"tile {gen['id']} completed with no image")
    p = download(base, urls[0], out / f"{_name(a.name, a.prompt)}.png")
    print(p)
    if a.projection != "isometric":
        print(f"  check the seams: um sprite tile-preview {p} <out.png>  (um sprite seamless blends the edges)")
    record(out, dict(kind="tile", generation_id=gen["id"], prompt=a.prompt, projection=a.projection,
                     collision=a.collision, size=png_size(p), file=str(p)))


def main(a):
    if a.cmd == "key":
        return cmd_key(a)
    base = base_url(a.url)
    if a.cmd == "credits":
        s = request(base, "GET", "/billing/status")
        left = (s.get("creditsLimit") or 0) - (s.get("creditsUsed") or 0)
        print(json.dumps(s, indent=2) if a.json else f"plan {s.get('plan')}: {left} of {s.get('creditsLimit')} credits left")
        return
    if a.cmd == "projects":
        ps = request(base, "GET", "/projects")
        if a.json:
            print(json.dumps(ps, indent=2))
            return
        for p in ps:
            print(f"{p.get('id')}  {p.get('name')!r}  {p.get('artStyle')} {p.get('viewAngle')} {p.get('resolution')}  "
                  f"{(p.get('_count') or {}).get('sprites', '?')} sprite(s)")
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    {"sprite": cmd_sprite, "animate": cmd_animate, "tile": cmd_tile}[a.cmd](a, base, out)


def register(sub):
    import argparse
    p = sub.add_parser("sprixen", help="2D sprites with Sprixen: one style per project, animation sheets, terrain tiles",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")

    def cmd(name, help_, out=True):
        q = cs.add_parser(name, help=help_)
        q.add_argument("--url", help=f"API address (default: $SPRIXEN_API_URL or {DEFAULT_URL})")
        if out:
            q.add_argument("--out", default="assets/gen", help="output folder (default assets/gen)")
            q.add_argument("--name", help="output file stem")
            q.add_argument("--timeout", type=float, default=900, help="seconds to wait for the result")
        q.set_defaults(func=main)
        return q

    q = cmd("credits", "plan and credits left", out=False)
    q.add_argument("--json", action="store_true")
    q = cmd("projects", "list your style projects", out=False)
    q.add_argument("--json", action="store_true")
    q = cmd("sprite", "text -> sprite(s) on a transparent background, in a style project (2 credits each)")
    q.add_argument("prompt")
    q.add_argument("--project", help="project name or id (default: one named after --style and --view)")
    q.add_argument("--style", default="pixel_art", choices=STYLES, help="art style of a new project")
    q.add_argument("--view", default="side_scroll", choices=VIEWS, help="view angle of a new project")
    q.add_argument("--size", choices=SIZES, help="sprite resolution (default: the project's, else 128x128)")
    q.add_argument("--palette", help="new project palette: a preset (nes, snes, gameboy, pico8) or #hex,#hex,...")
    q.add_argument("--variants", type=int, default=1, choices=[1, 2, 3])
    q.add_argument("--ref", help="reference image URL to match (style or character)")
    q.add_argument("--pixel-perfect", default="auto", choices=["auto", "on", "off"],
                   help="downscale kernel: on = nearest neighbour (crisp pixels), off = smooth")
    q.add_argument("--no-base", action="store_true", help="no pedestal or ground under the subject")
    q = cmd("animate", "sprite id -> animation sheet, one row of frames (4 credits, premium 8)")
    q.add_argument("sprite_id")
    q.add_argument("--type", default="idle", choices=ANIMATIONS)
    q.add_argument("--direction", choices=DIRECTIONS, help="default: keep the sprite's facing (left and right are not "
                   "re-checked, so generate the sprite facing the way the engine wants)")
    q.add_argument("--frames", type=int, help="2-12 (default 8)")
    q.add_argument("--fps", type=int, help="4-60 (default 12)")
    q.add_argument("--custom", help="what the character does, for --type custom")
    q.add_argument("--archetype", choices=["humanoid_biped", "quadruped", "winged", "amorphous", "serpentine"])
    q.add_argument("--weapon-type", help="e.g. sword, staff, bow")
    q.add_argument("--weapon-hand", choices=["left", "right", "both"])
    q.add_argument("--shield", action="store_true")
    q.add_argument("--size", choices=SIZES, help="frame resolution (default: the size of the sprite)")
    q.add_argument("--premium", action="store_true", help="smoother video-based animation, 96 frames at 24 fps (8 credits)")
    q = cmd("tile", "text -> terrain tile, top-down, side-view or isometric (1 credit)")
    q.add_argument("prompt")
    q.add_argument("--projection", default="top_down", choices=["top_down", "side_view", "isometric"])
    q.add_argument("--collision", default="walkable", choices=["walkable", "solid", "water"])
    q.add_argument("--category", default="terrain", choices=["terrain", "decoration", "entity"])
    q.add_argument("--flat", action="store_true", help="isometric only: a flat tile without raised block sides")

    kp = cs.add_parser("key", help="store / inspect the Sprixen API key (OS keyring first)",
                       description="`um sprixen` takes the key from SPRIXEN_API_KEY first, then from a file named by "
                                   "UM_SPRIXEN_KEY_FILE, then from the OS keyring (libsecret's secret-tool, as `um fal "
                                   "key` uses: Linux), then from ~/.secrets/sprixen-key (owner-only, what `um sprixen "
                                   "key set` writes where there's no keyring), then from SPRIXEN_API_KEY=... in a .env. "
                                   "Keys are never printed in full.")
    ka = kp.add_subparsers(dest="action", metavar="<action>")
    ks = ka.add_parser("set", help="store a key from a hidden prompt (or --from-file)")
    ks.add_argument("--from-file", metavar="PATH")
    ks.add_argument("--file-only", action="store_true", help="skip the OS keyring; write the owner-only key file")
    ka.add_parser("status", help="show every source and which one is active (keys are masked)")
    ka.add_parser("clear", help="delete the stored key (keyring entry and key file)")
    kp.set_defaults(func=main, cmd="key", action="status")
    for _a in ka.choices.values():
        _a.set_defaults(func=main, cmd="key")
