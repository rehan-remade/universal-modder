"""Game assets from fal (https://fal.ai): plain REST, no SDK needed. Needs FAL_KEY (env or a .env file).

    um fal sprite "a rusty scrap drone enemy, side view facing left, 16-bit pixel art" --out assets/gen --name drone
    um fal image "key art: ..." --aspect 16:9
    um fal edit "same drone, rotors blurred, second animation frame" --ref assets/gen/drone.png
    um fal rmbg in.png                       # background removal (BiRefNet v2)
    um fal pixelate in.png --colors 24       # image -> clean pixel art (grid-snapped, palette-limited)
    um fal texture "mossy cobblestone"       # seamless tiling texture
    um fal pbr "rusted sheet metal"          # basecolor/normal/roughness/metalness/height maps
    um fal model3d concept.png               # image -> textured GLB (Trellis 2; --engine hunyuan|tripo|meshy)
    um fal rig character.glb --animate       # auto-rig a humanoid (Meshy) -> rigged GLB/FBX + animations
    um fal sfx "laser rifle shot, sci-fi, punchy" --seconds 1.5
    um fal music "tense boss battle, chiptune, 140 bpm" --seconds 60
    um fal voice "You dare challenge the Mothership?" --voice-id Adam
    um fal video still.png "camera orbits the boss as it powers up"
    um fal run <endpoint> key=value key:=json image_url=@local.png   # anything else
    um fal search "image to 3d" | um fal schema fal-ai/trellis-2 | um fal price fal-ai/trellis-2

Every call appends a line to <out>/fal_manifest.jsonl (endpoint, inputs, request id, seed, files) so an
asset can be traced and regenerated. Local files passed as inputs are uploaded to fal storage first.
Model ids move fast: `um fal search` / the fal MCP's search_models find the current best.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from um.common import die

QUEUE = "https://queue.fal.run"
REST = "https://rest.fal.ai"
CDN = "https://v3.fal.media"
PLATFORM = "https://api.fal.ai/v1"
OPENAPI = "https://fal.ai/api/openapi/queue/openapi.json"

# Defaults per recipe (checked against the fal catalog 2026-09; override any with --model).
MODELS = {
    "image": "fal-ai/nano-banana-2",
    "sprite": "openai/gpt-image-2",              # supports background=transparent
    "edit": "fal-ai/nano-banana-2/edit",
    "rmbg": "fal-ai/birefnet/v2",
    "pixelate": "fal-ai/image2pixel",
    "upscale": "fal-ai/seedvr/upscale/image",
    "texture": "fal-ai/z-image/turbo/tiling",
    "pbr": "fal-ai/patina/material",
    "model3d": "fal-ai/trellis-2",
    "rig": "fal-ai/meshy/rigging",
    "sfx": "fal-ai/elevenlabs/sound-effects/v2",
    "music": "elevenlabs/music/v2.5",
    "voice": "fal-ai/elevenlabs/tts/eleven-v3",
    "video": "bytedance/seedance-2.5/image-to-video",
}
MODEL3D = {
    "trellis2": ("fal-ai/trellis-2", "image_url"),
    "hunyuan": ("fal-ai/hunyuan-3d/v3.1/pro/image-to-3d", "input_image_url"),
    "tripo": ("tripo3d/h3.1/image-to-3d", "image_url"),
    "meshy": ("meshy/v7.1/image-to-3d", "image_url"),
}
SPRITE_STYLE = ("a single game sprite, the whole subject in frame and centered, clean readable silhouette, "
                "no text, no watermark, no ground shadow, no background scenery")


# --------------------------------------------------------------------------- auth + http


def fal_key() -> str:
    k = os.environ.get("FAL_KEY")
    if not k and os.environ.get("FAL_KEY_FILE"):
        k = Path(os.environ["FAL_KEY_FILE"]).expanduser().read_text().strip()
    if not k:
        for env in (Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"):
            if env.exists():
                m = re.search(r"^\s*FAL_KEY\s*=\s*['\"]?([^'\"\s]+)", env.read_text(), re.M)
                if m:
                    k = m.group(1)
                    break
    if not k:
        die("FAL_KEY is not set. Create a key at https://fal.ai/dashboard/keys and `export FAL_KEY=...` "
            "(or put FAL_KEY=... in a .env file here)")
    return k


def _req(method: str, url: str, body=None, headers=None, auth=True, raw=False, timeout=120):
    h = {"Accept": "application/json", **(headers or {})}
    if auth:
        h["Authorization"] = "Key " + fal_key()
    data = None
    if body is not None:
        if isinstance(body, (bytes, bytearray)):
            data = bytes(body)
        else:
            data = json.dumps(body).encode()
            h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = r.read()
                return payload if raw else (json.loads(payload) if payload else {})
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:1500]
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            die(f"fal {method} {url.split('?')[0]} -> HTTP {e.code}: {detail}")
        except urllib.error.URLError as e:
            if attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            die(f"fal {method} {url}: {e.reason}")


# --------------------------------------------------------------------------- files


def _upload_cdn(name: str, ctype: str, data: bytes) -> str:
    """fal's CDN (the route fal-client uses): a short-lived upload token, then one POST of the bytes."""
    tok = _req("POST", f"{REST}/storage/auth/token?storage_type=fal-cdn-v3", {})
    req = urllib.request.Request(f"{CDN}/files/upload", data=data, method="POST", headers={
        "Authorization": f"{tok['token_type']} {tok['token']}", "Content-Type": ctype, "X-Fal-File-Name": name,
        "Accept": "application/json", "User-Agent": "universal-modder"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["access_url"]


def upload(path: str | Path) -> str:
    """Local file -> URL fal models can read (fal storage). Small files fall back to a data URI."""
    p = Path(path)
    if not p.is_file():
        die(f"no such file: {p}")
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    if p.suffix.lower() == ".glb":
        ctype = "model/gltf-binary"
    data = p.read_bytes()
    try:
        return _upload_cdn(p.name, ctype, data)
    except SystemExit:  # _req already printed why
        err = "see above"
    except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
        err = str(e)
    if len(data) < 8 << 20:
        print(f"fal upload failed ({err}); sending {p.name} inline as a data URI", file=sys.stderr)
        return f"data:{ctype};base64,{base64.b64encode(data).decode()}"
    die(f"could not upload {p.name} ({len(data):,} bytes) to fal storage ({err}); the data-URI fallback only covers files under 8 MiB")


def _as_url(v: str) -> str:
    """'@path' or an existing local path -> uploaded URL; URLs pass through."""
    if isinstance(v, str) and v.startswith("@"):
        return upload(v[1:])
    if isinstance(v, str) and not re.match(r"^(https?|data):", v) and Path(v).is_file():
        return upload(v)
    return v


def _urls_in(obj, trail=""):
    """Yield (json_path, url, content_type) for every downloadable file in a result."""
    if isinstance(obj, dict):
        u = obj.get("url")
        if isinstance(u, str) and u.startswith("http"):
            yield trail, u, obj.get("content_type") or ""
        for k, v in obj.items():
            if k != "url":
                yield from _urls_in(v, f"{trail}.{k}" if trail else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _urls_in(v, f"{trail}[{i}]")


EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif", "audio/mpeg": ".mp3", "audio/wav": ".wav",
       "audio/x-wav": ".wav", "video/mp4": ".mp4", "model/gltf-binary": ".glb", "application/octet-stream": ""}


def download_outputs(result: dict, out: Path, name: str) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    files, used, first_key, failed = [], set(), None, []
    for trail, url, ctype in _urls_in(result):
        ext = Path(urllib.parse.urlparse(url).path).suffix or EXT.get(ctype.split(";")[0], "")
        key = re.sub(r"\[\d+\]", "", trail).split(".")[-1] or "file"
        idx = re.findall(r"\[(\d+)\]", trail)
        first_key = first_key or key
        # images[0] -> name, images[1] -> name_2; other outputs (mask, thumbnail, fbx) -> name_<key>
        if key == first_key:
            stem = name if not idx or idx[-1] == "0" else f"{name}_{int(idx[-1]) + 1}"
        else:
            stem = f"{name}_{key}" + (f"_{int(idx[-1]) + 1}" if idx and idx[-1] != "0" else "")
        path = out / f"{stem}{ext}"
        n = 1
        while path.name in used:
            n += 1
            path = out / f"{stem}_{n}{ext}"
        used.add(path.name)
        req = urllib.request.Request(url, headers={"User-Agent": "universal-modder"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                path.write_bytes(r.read())
        except (urllib.error.URLError, OSError) as e:  # keep going: the other outputs are still worth saving
            failed.append(f"{url} ({e})")
            continue
        files.append(str(path))
    if failed:
        rid, ep = result.get("_request_id"), result.get("_endpoint") or "<endpoint>"
        die("the job finished but these outputs did not download:\n  " + "\n  ".join(failed) +
            (f"\nrequest {rid}: try again later with `um fal result {ep} {rid}`" if rid else ""))
    return files


# --------------------------------------------------------------------------- queue


def submit(endpoint: str, inp: dict) -> dict:
    return _req("POST", f"{QUEUE}/{endpoint}", inp)


def run(endpoint: str, inp: dict, timeout: float = 1800, quiet: bool = False) -> dict:
    """Submit to the queue, poll (printing logs to stderr), return the result JSON."""
    job = submit(endpoint, inp)
    rid = job.get("request_id")
    status_url = job.get("status_url") or f"{QUEUE}/{endpoint}/requests/{rid}/status"
    response_url = job.get("response_url") or f"{QUEUE}/{endpoint}/requests/{rid}"
    t0, seen, last = time.time(), 0, ""
    while True:
        st = _req("GET", status_url + ("&" if "?" in status_url else "?") + "logs=1")
        s = st.get("status")
        logs = st.get("logs") or []
        if not quiet:
            for line in logs[seen:]:
                msg = (line or {}).get("message", "")
                if msg:
                    print(f"  [{endpoint}] {msg}", file=sys.stderr)
            if s != last:
                pos = f" (queue position {st.get('queue_position')})" if s == "IN_QUEUE" and st.get("queue_position") is not None else ""
                print(f"  [{endpoint}] {s}{pos}", file=sys.stderr)
        seen, last = len(logs), s
        if s == "COMPLETED":
            if st.get("error"):
                die(f"{endpoint} failed: {st['error']}")
            res = _req("GET", response_url)
            res["_request_id"], res["_endpoint"] = rid, endpoint
            return res
        if time.time() - t0 > timeout:
            die(f"{endpoint}: still {s} after {timeout:.0f}s (request {rid}); check later with `um fal result {endpoint} {rid}`")
        time.sleep(1.0 if time.time() - t0 < 30 else 3.0)


def generate(endpoint: str, inp: dict, out: str | Path, name: str, quiet=False) -> dict:
    """run + download every output file + manifest line. Returns {'files': [...], 'result': {...}}."""
    inp = {k: ([_as_url(x) for x in v] if isinstance(v, list) and k.endswith("urls") else _as_url(v) if k.endswith("url") else v)
           for k, v in inp.items() if v is not None}
    res = run(endpoint, inp, quiet=quiet)
    out = Path(out)
    files = download_outputs(res, out, name)
    rec = dict(t=time.strftime("%Y-%m-%dT%H:%M:%S"), endpoint=endpoint, name=name, request_id=res.get("_request_id"),
               seed=res.get("seed"), files=files,
               input={k: (v[:120] + "..." if isinstance(v, str) and v.startswith("data:") else v) for k, v in inp.items()})
    with open(out / "fal_manifest.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    for p in files:
        print(p)
    return dict(files=files, result=res)


# --------------------------------------------------------------------------- catalog


def search(q: str, category: str | None = None, limit: int = 20) -> list[dict]:
    params = {"q": q, "status": "active", "limit": limit}
    if category:
        params["category"] = category
    r = _req("GET", f"{PLATFORM}/models?" + urllib.parse.urlencode(params))
    return [dict(endpoint=m.get("endpoint_id"), name=(m.get("metadata") or {}).get("display_name"),
                 category=(m.get("metadata") or {}).get("category"), date=((m.get("metadata") or {}).get("date") or "")[:10])
            for m in r.get("models", [])]


def schema(endpoint: str) -> dict:
    """Input fields (type, default, enum) and output fields of an endpoint, from its public OpenAPI."""
    api = json.loads(_req("GET", OPENAPI + "?" + urllib.parse.urlencode({"endpoint_id": endpoint}), auth=False, raw=True))
    comps = api.get("components", {}).get("schemas", {})

    def resolve(ref):
        return comps.get(ref.split("/")[-1], {}) if ref else {}

    inp = out = {}
    for path, ops in api.get("paths", {}).items():
        post = ops.get("post")
        if post and "requestBody" in post and not inp:
            inp = resolve(post["requestBody"]["content"]["application/json"]["schema"].get("$ref"))
        if path.endswith("/requests/{request_id}") and "get" in ops:
            try:
                out = resolve(ops["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"])
            except KeyError:
                pass

    def fields(s):
        res = {}
        for k, v in (s.get("properties") or {}).items():
            d = {x: v[x] for x in ("type", "default", "enum", "description") if x in v}
            if "anyOf" in v:
                d["type"] = " | ".join(a.get("type") or a.get("$ref", "").split("/")[-1] for a in v["anyOf"])
            if "$ref" in v:
                d["type"] = v["$ref"].split("/")[-1]
            if "description" in d:
                d["description"] = d["description"][:160]
            res[k] = d
        return res

    return dict(endpoint=endpoint, required=inp.get("required", []), input=fields(inp), output=fields(out))


def price(endpoint: str) -> dict:
    return _req("GET", f"{PLATFORM}/models/pricing?" + urllib.parse.urlencode({"endpoint_id": endpoint}))


# --------------------------------------------------------------------------- recipes


def _kv(pairs: list[str]) -> dict:
    """key=value (string) and key:=json (number/bool/list/object); value '@file' uploads a local file."""
    out = {}
    for p in pairs or []:
        if ":=" in p:
            k, v = p.split(":=", 1)
            out[k] = json.loads(v)
        elif "=" in p:
            k, v = p.split("=", 1)
            out[k] = v
        else:
            die(f"bad argument {p!r}: use key=value or key:=json")
    return out


def _name(args, fallback: str) -> str:
    if getattr(args, "name", None):
        return args.name
    words = re.sub(r"[^a-z0-9 ]", "", fallback.lower()).split()[:5]
    return "_".join(words) or "asset"


def cmd(args):
    r = args.recipe
    out = getattr(args, "out", "assets/gen")
    extra = _kv(getattr(args, "set", None))
    model = getattr(args, "model", None)
    if r == "search":
        for m in search(args.query, args.category, args.limit):
            print(f"{m['endpoint']:55} {m['category'] or '':18} {m['date']}  {m['name']}")
        return
    if r == "schema":
        print(json.dumps(schema(args.endpoint), indent=2))
        return
    if r == "price":
        print(json.dumps(price(args.endpoint), indent=2))
        return
    if r == "result":
        res = _req("GET", f"{QUEUE}/{args.endpoint}/requests/{args.request_id}")
        download_outputs(res, Path(out), args.name or args.request_id)
        print(json.dumps(res, indent=2))
        return
    if r == "upload":
        print(upload(args.file))
        return
    if r == "run":
        inp = _kv(args.params)
        generate(args.endpoint, inp, out, args.name or args.endpoint.split("/")[-1])
        return

    if r == "image":
        inp = dict(prompt=args.prompt, aspect_ratio=args.aspect, resolution=args.res, num_images=args.n, seed=args.seed)
        generate(model or MODELS["image"], {**inp, **extra}, out, _name(args, args.prompt))
    elif r == "sprite":
        prompt = f"{args.prompt}. {SPRITE_STYLE}"
        ep = model or MODELS["sprite"]
        if ep.startswith("openai/gpt-image"):
            inp = dict(prompt=prompt, background="transparent", quality=args.quality, image_size=args.size, num_images=args.n, output_format="png")
        else:
            inp = dict(prompt=prompt + ", on a plain flat white background", num_images=args.n)
        res = generate(ep, {**inp, **extra}, out, _name(args, args.prompt))
        if not ep.startswith("openai/gpt-image"):
            for f in res["files"]:
                generate(MODELS["rmbg"], dict(image_url=f, output_format="png"), out, Path(f).stem + "_cut")
    elif r == "edit":
        inp = dict(prompt=args.prompt, image_urls=args.ref, num_images=args.n, aspect_ratio=args.aspect, resolution=args.res, seed=args.seed)
        generate(model or MODELS["edit"], {**inp, **extra}, out, _name(args, args.prompt))
    elif r == "rmbg":
        generate(model or MODELS["rmbg"], {**dict(image_url=args.image, output_format="png"), **extra}, out, args.name or Path(args.image).stem + "_cut")
    elif r == "pixelate":
        inp = dict(image_url=args.image, max_colors=args.colors, transparent_background=True, trim_borders=True, scale=args.scale)
        generate(model or MODELS["pixelate"], {**inp, **extra}, out, args.name or Path(args.image).stem + "_px")
    elif r == "upscale":
        inp = dict(image_url=args.image, upscale_factor=args.factor, output_format="png")
        generate(model or MODELS["upscale"], {**inp, **extra}, out, args.name or Path(args.image).stem + "_up")
    elif r == "texture":
        inp = dict(prompt=f"{args.prompt}, seamless tileable texture, top-down, even lighting", image_size=args.size, tiling_mode=args.tiling)
        generate(model or MODELS["texture"], {**inp, **extra}, out, _name(args, args.prompt))
    elif r == "pbr":
        inp = dict(prompt=args.prompt, maps=args.maps.split(","), image_size=args.size, tiling_mode="both")
        generate(model or MODELS["pbr"], {**inp, **extra}, out, _name(args, args.prompt))
    elif r == "model3d":
        ep, field = MODEL3D[args.engine]
        inp = {field: args.image}
        if args.engine == "trellis2":
            inp.update(texture_size=args.texture, decimation_target=args.faces)
        elif args.engine == "hunyuan":
            inp.update(face_count=args.faces, enable_pbr=True)
        generate(model or ep, {**inp, **extra}, out, args.name or Path(args.image).stem)
    elif r == "rig":
        inp = dict(model_url=args.model_file, enable_animation=args.animate, height_meters=args.height)
        generate(model or MODELS["rig"], {**inp, **extra}, out, args.name or Path(args.model_file).stem + "_rigged")
    elif r == "sfx":
        inp = dict(text=args.prompt, duration_seconds=args.seconds, loop=args.loop, output_format="mp3_44100_192")
        generate(model or MODELS["sfx"], {**inp, **extra}, out, _name(args, args.prompt))
    elif r == "music":
        inp = dict(prompt=args.prompt, music_length_ms=int(args.seconds * 1000), force_instrumental=not args.vocals, output_format="mp3_44100_192")
        generate(model or MODELS["music"], {**inp, **extra}, out, _name(args, args.prompt))
    elif r == "voice":
        inp = dict(text=args.text, voice=args.voice_id, stability=args.stability)
        generate(model or MODELS["voice"], {**inp, **extra}, out, _name(args, args.text))
    elif r == "video":
        inp = dict(image_url=args.image, prompt=args.prompt, duration=str(args.seconds), resolution=args.res, generate_audio=args.audio)
        generate(model or MODELS["video"], {**inp, **extra}, out, args.name or Path(args.image).stem + "_video")


def register(sub):
    p = sub.add_parser("fal", help="generate assets with fal (sprites, textures, 3D, rigs, audio, video)",
                       description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    rs = p.add_subparsers(dest="recipe", metavar="<recipe>")

    def recipe(name, help_, *positional, out=True):
        q = rs.add_parser(name, help=help_)
        for pos in positional:
            q.add_argument(pos)
        if out:
            q.add_argument("--out", default="assets/gen", help="output folder (default assets/gen)")
            q.add_argument("--name", help="output file stem")
            q.add_argument("--model", help="override the endpoint")
            q.add_argument("--set", action="append", metavar="K=V", help="extra model input (repeatable; K:=json for numbers)")
        q.set_defaults(func=cmd)
        return q

    q = recipe("image", "text -> image (Nano Banana 2)", "prompt")
    q.add_argument("--aspect", default="1:1", help="e.g. 1:1, 16:9, 3:4, 21:9")
    q.add_argument("--res", default="1K", choices=["0.5K", "1K", "2K", "4K"])
    q.add_argument("--n", type=int, default=1)
    q.add_argument("--seed", type=int)
    q = recipe("sprite", "text -> sprite on a transparent background (GPT Image 2)", "prompt")
    q.add_argument("--quality", default="high", choices=["low", "medium", "high"])
    q.add_argument("--size", default="square_hd", help="square_hd, portrait_4_3, landscape_4_3, ...")
    q.add_argument("--n", type=int, default=1)
    q = recipe("edit", "edit / make variants of reference images (consistent sets, animation frames)", "prompt")
    q.add_argument("--ref", action="append", required=True, help="reference image (path or URL), repeatable")
    q.add_argument("--aspect", default="auto")
    q.add_argument("--res", default="1K", choices=["0.5K", "1K", "2K", "4K"])
    q.add_argument("--n", type=int, default=1)
    q.add_argument("--seed", type=int)
    recipe("rmbg", "remove the background (BiRefNet v2)", "image")
    q = recipe("pixelate", "image -> grid-snapped pixel art (fal image2pixel)", "image")
    q.add_argument("--colors", type=int, default=32)
    q.add_argument("--scale", type=int, help="force the pixel scale")
    q = recipe("upscale", "upscale an image (SeedVR2)", "image")
    q.add_argument("--factor", type=float, default=2)
    q = recipe("texture", "seamless tiling texture (Z-Image Turbo tiling)", "prompt")
    q.add_argument("--size", default="square_hd")
    q.add_argument("--tiling", default="both", choices=["both", "horizontal", "vertical"])
    q = recipe("pbr", "PBR material maps (PATINA)", "prompt")
    q.add_argument("--maps", default="basecolor,normal,roughness,metalness,height")
    q.add_argument("--size", default="square_hd")
    q = recipe("model3d", "image -> textured 3D model (GLB)", "image")
    q.add_argument("--engine", default="trellis2", choices=list(MODEL3D))
    q.add_argument("--texture", type=int, default=2048, choices=[1024, 2048, 4096])
    q.add_argument("--faces", type=int, default=100_000, help="target face count (game-ready: 5k-50k)")
    q = recipe("rig", "auto-rig a humanoid model (Meshy), optionally with animations", "model_file")
    q.add_argument("--animate", action="store_true")
    q.add_argument("--height", type=float, default=1.7, help="character height in meters")
    q = recipe("sfx", "sound effect (ElevenLabs SFX v2)", "prompt")
    q.add_argument("--seconds", type=float)
    q.add_argument("--loop", action="store_true")
    q = recipe("music", "music track (ElevenLabs Music)", "prompt")
    q.add_argument("--seconds", type=float, default=60)
    q.add_argument("--vocals", action="store_true")
    q = recipe("voice", "voice line / narration (ElevenLabs v3)", "text")
    q.add_argument("--voice-id", default="Rachel")
    q.add_argument("--stability", type=float, default=0.5)
    q = recipe("video", "image -> video clip (Seedance 2.5): trailers, cutscenes", "image", "prompt")
    q.add_argument("--seconds", type=int, default=5)
    q.add_argument("--res", default="720p", choices=["480p", "720p", "1080p"])
    q.add_argument("--audio", action="store_true")
    q = recipe("run", "any endpoint: key=value / key:=json / key=@file", "endpoint")
    q.add_argument("params", nargs="*")
    q = recipe("search", "search the fal catalog", "query", out=False)
    q.add_argument("--category", help="text-to-image, image-to-3d, text-to-audio, ...")
    q.add_argument("--limit", type=int, default=20)
    recipe("schema", "input/output fields of an endpoint", "endpoint", out=False)
    recipe("price", "pricing of an endpoint", "endpoint", out=False)
    q = recipe("result", "fetch (and download) a finished request", "endpoint", "request_id")
    recipe("upload", "upload a local file, print its URL", "file", out=False)
