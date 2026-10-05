"""Images from a local ComfyUI server: no API key, runs on your own GPU (https://www.comfy.org).

    um comfy status                                   # is ComfyUI up? which checkpoints can it load?
    um comfy image "a rusty scrap drone enemy, side view, 16-bit pixel art" --name drone
    um comfy image "a red health potion" --sprite     # plain background, then cut out locally (um sprite cutout)
    um comfy image "mossy dungeon wall" --checkpoint sd_xl_base_1.0.safetensors --size 1024x1024 --steps 30
    um comfy run my_workflow.json --set 6.text="a blue mana potion" --set 3.seed:=42 --name potion

Start ComfyUI first. It listens on http://127.0.0.1:8188; use --url or COMFYUI_URL for another address.
`image` runs ComfyUI's default text-to-image graph (checkpoint, two prompts, KSampler, VAE decode), which
fits SD 1.5 and SDXL checkpoints. Without --checkpoint it takes the first one the server lists. For anything
else (Flux, img2img, ControlNet, LoRAs), build the graph in ComfyUI, save it with Export (API) and run it
with `um comfy run`. --set NODE.INPUT=value changes a node input first: NODE is the node id or its title,
and := takes JSON (numbers, true/false). Files land in --out (default assets/gen), and each call appends a
line to <out>/comfy_manifest.jsonl (workflow, seed, files) so an image can be traced and made again.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from um.common import die, parse_size

DEFAULT_URL = "http://127.0.0.1:8188"
NEGATIVE = "blurry, low quality, jpeg artifacts, watermark, text, signature"


def base_url(url: str | None = None) -> str:
    return (url or os.environ.get("COMFYUI_URL") or DEFAULT_URL).rstrip("/")


def _describe(err: dict) -> str:
    """ComfyUI's validation error (top-level error + node_errors) as one readable line per problem."""
    lines = []
    e = err.get("error")
    if isinstance(e, dict):
        lines.append(" ".join(x for x in (e.get("message"), e.get("details")) if x))
    elif e:
        lines.append(str(e))
    for node, ne in (err.get("node_errors") or {}).items():
        for x in ne.get("errors", []):
            lines.append(f"node {node} ({ne.get('class_type', '?')}): {x.get('message', '')}: {x.get('details', '')}".rstrip(": "))
    return "\n  ".join(lines) or json.dumps(err)[:1500]


def _req(base: str, path: str, body=None, raw: bool = False, timeout: float = 60, missing_ok: bool = False):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(base + path, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = r.read()
            return payload if raw else (json.loads(payload) if payload else {})
    except urllib.error.HTTPError as e:
        if missing_ok and e.code == 404:
            return None
        detail = e.read().decode(errors="replace")
        try:
            err = json.loads(detail)
        except ValueError:
            err = None
        if path == "/prompt" and isinstance(err, dict) and (err.get("error") or err.get("node_errors")):
            die("ComfyUI rejected the workflow:\n  " + _describe(err))
        die(f"ComfyUI {path.split('?')[0]} -> HTTP {e.code}: {detail[:1500]}")
    except urllib.error.URLError as e:
        die(f"no ComfyUI at {base} ({e.reason}). Start it (python main.py in the ComfyUI folder), or pass --url / "
            "set COMFYUI_URL")


# --------------------------------------------------------------------------- server info


def _combo(spec) -> list[str]:
    """Options of a COMBO input in /object_info: [[a, b], {...}] (classic) or ["COMBO", {"options": [a, b]}] (v3)."""
    if isinstance(spec, list) and spec:
        if isinstance(spec[0], list):
            return [str(x) for x in spec[0]]
        if len(spec) > 1 and isinstance(spec[1], dict):
            return [str(x) for x in spec[1].get("options", [])]
    return []


def checkpoints(base: str) -> list[str]:
    names = _req(base, "/models/checkpoints", missing_ok=True)   # older servers have no /models route
    if isinstance(names, list):
        return [str(x) for x in names]
    info = _req(base, "/object_info/CheckpointLoaderSimple")
    return _combo(info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name"))


def status(base: str) -> dict:
    stats = _req(base, "/system_stats")
    system = stats.get("system", {})
    return dict(url=base, version=system.get("comfyui_version"), pytorch=system.get("pytorch_version"),
                devices=[f"{d.get('name')} ({d.get('type')})" for d in stats.get("devices", [])], checkpoints=checkpoints(base))


# --------------------------------------------------------------------------- workflows


def txt2img(prompt: str, checkpoint: str, negative: str = NEGATIVE, width: int = 512, height: int = 512, steps: int = 25,
            cfg: float = 7.0, seed: int = 0, sampler: str = "euler", scheduler: str = "normal", n: int = 1) -> dict:
    """ComfyUI's default graph in API format (same node ids as the stock workflow)."""
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": n}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "3": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": steps, "cfg": cfg, "sampler_name": sampler,
                                                    "scheduler": scheduler, "denoise": 1.0, "model": ["4", 0],
                                                    "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "um", "images": ["8", 0]}},
    }


def load_workflow(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        die(f"no such workflow: {p}")
    try:
        wf = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        die(f"{p} is not JSON: {e}")
    if isinstance(wf, dict) and "nodes" in wf and "links" in wf:
        die(f"{p} is a UI workflow. In ComfyUI, save it with Export (API) and run that file")
    if isinstance(wf, dict) and isinstance(wf.get("prompt"), dict):
        wf = wf["prompt"]
    if not isinstance(wf, dict) or not wf or not all(isinstance(v, dict) and "class_type" in v for v in wf.values()):
        die(f"{p} is not an API-format workflow (a JSON object of nodes, each with class_type and inputs)")
    return wf


def _node(wf: dict, ref: str) -> str:
    if ref in wf:
        return ref
    hits = [k for k, v in wf.items() if str(v.get("_meta", {}).get("title", "")).lower() == ref.lower()]
    if len(hits) == 1:
        return hits[0]
    known = ", ".join(f"{k} ({v.get('_meta', {}).get('title') or v.get('class_type')})" for k, v in wf.items())
    die(f"{'several nodes are' if hits else 'no node is'} called {ref!r}; nodes: {known}")


def apply_set(wf: dict, sets: list[str] | None) -> dict:
    """NODE.INPUT=value (a string) or NODE.INPUT:=json, NODE being a node id or title. Returns a changed copy."""
    wf = json.loads(json.dumps(wf))
    for s in sets or []:
        left, eq, val = s.partition("=")
        json_val = left.endswith(":")
        left = left[:-1] if json_val else left
        ref, dot, key = left.rpartition(".")
        if not eq or not dot or not ref or not key:
            die(f"bad --set {s!r}: use NODE.INPUT=value or NODE.INPUT:=json")
        if json_val:
            try:
                val = json.loads(val)
            except ValueError:
                die(f"--set {s!r}: {val!r} is not JSON")
        wf[_node(wf, ref)].setdefault("inputs", {})[key] = val
    return wf


# --------------------------------------------------------------------------- run


def queue(base: str, wf: dict) -> str:
    res = _req(base, "/prompt", {"prompt": wf, "client_id": uuid.uuid4().hex})
    if res.get("node_errors"):
        die("ComfyUI rejected the workflow:\n  " + _describe(res))
    if not res.get("prompt_id"):
        die(f"ComfyUI didn't queue the workflow: {json.dumps(res)[:1500]}")
    return res["prompt_id"]


def wait(base: str, prompt_id: str, timeout: float = 1800, poll: float = 1.0) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        h = _req(base, f"/history/{prompt_id}").get(prompt_id)
        if h:
            st = h.get("status", {})
            if st.get("status_str") == "error":
                msgs = [d for kind, d in st.get("messages", []) if kind == "execution_error"]
                e = msgs[0] if msgs else {}
                die(f"ComfyUI failed in node {e.get('node_id', '?')} ({e.get('node_type', '?')}): "
                    f"{e.get('exception_message', 'see the ComfyUI console')}".strip())
            if st.get("completed", True):
                return h
        time.sleep(poll)
    die(f"ComfyUI didn't finish in {timeout:.0f} s (prompt {prompt_id}); it is still queued or running")


def outputs(history: dict) -> list[dict]:
    """Every file a run produced ({filename, subfolder, type}), in node order."""
    files = []
    for node in sorted(history.get("outputs", {}), key=lambda k: (len(k), k)):
        for items in history["outputs"][node].values():
            if isinstance(items, list):
                files += [x for x in items if isinstance(x, dict) and x.get("filename")]
    return files


def generate(base: str, wf: dict, out: str | Path, name: str, timeout: float = 1800, record: dict | None = None) -> list[str]:
    """Queue a workflow, wait, download every output into out/, append a manifest line. Returns the paths."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    pid = queue(base, wf)
    files = []
    for i, f in enumerate(outputs(wait(base, pid, timeout))):
        q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
        path = out / f"{name if i == 0 else f'{name}_{i + 1}'}{Path(f['filename']).suffix or '.png'}"
        path.write_bytes(_req(base, f"/view?{q}", raw=True, timeout=600))
        files.append(str(path))
    if not files:
        die(f"the workflow finished but saved nothing: add a SaveImage node (prompt {pid})")
    rec = dict(t=time.strftime("%Y-%m-%dT%H:%M:%S"), url=base, prompt_id=pid, name=name, files=files, **(record or {}), workflow=wf)
    with open(out / "comfy_manifest.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    for p in files:
        print(p)
    return files


def _name(args, fallback: str) -> str:
    if args.name:
        return args.name
    return "_".join(re.sub(r"[^a-z0-9 ]", "", fallback.lower()).split()[:5]) or "image"


def main(a):
    base = base_url(a.url)
    if a.cmd == "status":
        s = status(base)
        if a.json:
            print(json.dumps(s, indent=2))
            return
        print(f"ComfyUI {s['version'] or '?'} at {s['url']} (PyTorch {s['pytorch'] or '?'})")
        for d in s["devices"]:
            print(f"  device: {d}")
        print(f"  {len(s['checkpoints'])} checkpoint(s)" + "".join(f"\n    {c}" for c in s["checkpoints"]))
        return
    if a.cmd == "run":
        wf = apply_set(load_workflow(a.workflow), a.set)
        generate(base, wf, a.out, a.name or Path(a.workflow).stem, a.timeout, dict(source=str(a.workflow), set=a.set or []))
        return
    if a.cmd == "image":
        ckpt = a.checkpoint
        if not ckpt:
            names = checkpoints(base)
            if not names:
                die("ComfyUI lists no checkpoints: put one in ComfyUI/models/checkpoints, or run a workflow with `um comfy run`")
            ckpt = names[0]
        w, h = parse_size(a.size) if a.size else ((1024, 1024) if re.search(r"xl|1024", ckpt, re.I) else (512, 512))
        prompt = a.prompt
        if a.sprite:
            from um.fal import SPRITE_STYLE
            prompt = f"{prompt}. {SPRITE_STYLE}, on a plain flat white background"
        seed = a.seed if a.seed is not None else random.randrange(2**32)
        wf = txt2img(prompt, ckpt, a.negative, w, h, a.steps, a.cfg, seed, a.sampler, a.scheduler, a.n)
        name = _name(a, a.prompt)
        files = generate(base, wf, a.out, name, a.timeout, dict(prompt=prompt, checkpoint=ckpt, seed=seed))
        if a.sprite:
            from um import sprite
            for f in files:
                cut = Path(f).with_name(Path(f).stem + "_cut.png")
                sprite.cutout(sprite.load(f)).save(cut)
                print(cut)


def register(sub):
    import argparse
    p = sub.add_parser("comfy", help="generate images locally with ComfyUI (no API key)",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")

    def cmd(name, help_, out=True):
        q = cs.add_parser(name, help=help_)
        q.add_argument("--url", help=f"ComfyUI address (default: $COMFYUI_URL or {DEFAULT_URL})")
        if out:
            q.add_argument("--out", default="assets/gen", help="output folder (default assets/gen)")
            q.add_argument("--name", help="output file stem")
            q.add_argument("--timeout", type=float, default=1800, help="seconds to wait for the result")
        q.set_defaults(func=main)
        return q

    q = cmd("status", "is ComfyUI running, and which checkpoints can it load", out=False)
    q.add_argument("--json", action="store_true")
    q = cmd("image", "text -> image with ComfyUI's default graph (SD 1.5 / SDXL checkpoints)")
    q.add_argument("prompt")
    q.add_argument("--checkpoint", help="checkpoint file name (default: the first one the server lists)")
    q.add_argument("--negative", default=NEGATIVE)
    q.add_argument("--size", help="WxH (default 1024x1024 for SDXL-looking checkpoint names, else 512x512)")
    q.add_argument("--steps", type=int, default=25)
    q.add_argument("--cfg", type=float, default=7.0)
    q.add_argument("--seed", type=int, help="default: random (written to the manifest)")
    q.add_argument("--sampler", default="euler")
    q.add_argument("--scheduler", default="normal")
    q.add_argument("--n", type=int, default=1, help="images per run (batch size)")
    q.add_argument("--sprite", action="store_true", help="a single sprite on a plain background, then cut out locally")
    q = cmd("run", "run a workflow saved with Export (API), with --set overrides")
    q.add_argument("workflow")
    q.add_argument("--set", action="append", metavar="NODE.INPUT=V", help="change a node input (repeatable; := for JSON)")
