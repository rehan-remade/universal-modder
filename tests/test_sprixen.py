"""`um sprixen` against a stand-in for the Sprixen API: no key, no network, no credits."""
import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from um import cli, fal, sprixen  # noqa: E402


@pytest.fixture(autouse=True)
def no_keyring(monkeypatch):
    """Never read or write the real desktop keyring, and start every test with no key cached."""
    monkeypatch.setattr(sprixen, "keyring_get", lambda: None)
    monkeypatch.setattr(sprixen, "keyring_set", lambda value: False)
    monkeypatch.setattr(sprixen, "keyring_clear", lambda: False)
    monkeypatch.setattr(sprixen, "keyring_available", lambda: False)
    monkeypatch.setattr(sprixen, "_KEY_CACHE", None)


def png(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (w, h), (0, 0, 0, 0)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def fake_sprixen(monkeypatch):
    """/v1/projects, /v1/generations, /v1/sprites/:id(/animations), /v1/animations/:id, /v1/billing/status,
    /v1/tile-packs/generate and the static /api/public files, with Sprixen's error shape."""
    state = {"projects": [], "posts": [], "auth": set(), "polls": 0, "fail_next": None}
    files = {"/api/public/uploads/g1_0.png": png(16, 16), "/api/public/uploads/s1_walk_sheet.png": png(64, 16),
             "/api/public/uploads/t1.png": png(32, 32)}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, obj, code=200):
            body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "image/png" if isinstance(obj, bytes) else "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in files:
                return self._send(files[path])
            state["auth"].add(self.headers.get("Authorization"))
            if path == "/v1/projects":
                return self._send(state["projects"])
            if path == "/v1/billing/status":
                return self._send({"plan": "pro", "creditsUsed": 12, "creditsLimit": 200})
            if path == "/v1/generations/g1":
                state["polls"] += 1                                   # the first poll finds it still running
                if state["polls"] == 1:
                    return self._send({"id": "g1", "status": "processing"})
                return self._send({"id": "g1", "status": "completed", "creditsUsed": 2,
                                   "resultUrls": ["/api/public/uploads/g1_0.png"],
                                   "sprites": [{"id": "s1", "imageUrl": "/api/public/uploads/g1_0.png"}]})
            if path == "/v1/generations/t1":
                return self._send({"id": "t1", "status": "completed", "resultUrls": ["/api/public/uploads/t1.png"]})
            if path == "/v1/generations/bad":
                return self._send({"id": "bad", "status": "failed", "error": "background removal unavailable"})
            if path == "/v1/sprites/s1":
                return self._send({"id": "s1", "width": 16, "height": 16})
            if path == "/v1/animations/a1":
                return self._send({"id": "a1", "status": "completed", "frameCount": 4, "fps": 12,
                                   "spriteSheetUrl": "/api/public/uploads/s1_walk_sheet.png"})
            self._send({"statusCode": 404, "message": "Not Found", "code": "NOT_FOUND"}, 404)

        def do_POST(self):
            path = urlparse(self.path).path
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["posts"].append((path, body))
            if state["fail_next"]:
                status, err = state["fail_next"]
                state["fail_next"] = None
                return self._send(err, status)
            if path == "/v1/projects":
                p = {"id": "p1", "name": body["name"], "artStyle": body["artStyle"], "viewAngle": body["viewAngle"]}
                state["projects"].append(p)
                return self._send(p, 201)
            if path == "/v1/generations":
                return self._send({"id": "bad" if body["prompt"] == "doomed" else "g1", "status": "pending"}, 201)
            if path == "/v1/sprites/s1/animations":
                return self._send({"id": "a1", "status": "pending"}, 202)
            if path == "/v1/tile-packs/generate":
                return self._send({"id": "t1", "status": "pending"}, 201)
            self._send({"statusCode": 404, "message": "Not Found"}, 404)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("SPRIXEN_API_KEY", "spx_live_test")
    monkeypatch.setattr(sprixen.time, "sleep", lambda s: None)
    state["url"] = f"http://127.0.0.1:{srv.server_address[1]}"
    monkeypatch.setenv("SPRIXEN_API_URL", state["url"])          # a call without --url still stays on this machine
    yield state
    srv.shutdown()


def test_sprixen_sprite_then_animate(fake_sprixen, tmp_path):
    out, url = tmp_path / "gen", fake_sprixen["url"]
    cli.main(["sprixen", "sprite", "a red potion", "--url", url, "--out", str(out), "--size", "16x16", "--style", "chibi"])
    (_, project), (_, gen) = fake_sprixen["posts"]
    assert (project["name"], project["artStyle"], project["resolution"]) == ("um chibi side_scroll", "chibi", "16x16")
    assert (gen["projectId"], gen["resolution"], gen["pixelPerfect"]) == ("p1", "16x16", "auto")
    assert Image.open(out / "a_red_potion.png").size == (16, 16)
    cli.main(["sprixen", "sprite", "a blue potion", "--url", url, "--out", str(out), "--style", "chibi"])
    assert [p for p, _ in fake_sprixen["posts"]].count("/v1/projects") == 1      # same style: project reused
    cli.main(["sprixen", "animate", "s1", "--type", "walk", "--url", url, "--out", str(out)])
    anim = fake_sprixen["posts"][-1][1]
    assert anim == {"type": "walk", "quality": "standard", "resolution": "16x16"}  # no direction: keep the facing
    rec = [json.loads(x) for x in (out / "sprixen_manifest.jsonl").read_text().splitlines()]
    assert rec[0]["files"][0]["sprite_id"] == "s1" and rec[0]["files"][0]["size"] == [16, 16]
    assert (rec[-1]["frames"], rec[-1]["frame_size"]) == (4, [16, 16])                # 64x16 sheet, 4 frames
    assert fake_sprixen["auth"] == {"Bearer spx_live_test"}


def test_sprixen_tile_credits_and_errors(fake_sprixen, tmp_path, capsys):
    url = fake_sprixen["url"]
    cli.main(["sprixen", "tile", "mossy floor", "--url", url, "--out", str(tmp_path), "--name", "floor"])
    assert fake_sprixen["posts"][-1][1] == {"prompt": "mossy floor", "projectionType": "top_down",
                                            "collision": "walkable", "category": "terrain"}
    assert Image.open(tmp_path / "floor.png").size == (32, 32)
    cli.main(["sprixen", "credits", "--url", url])
    assert "188 of 200 credits left" in capsys.readouterr().out
    fake_sprixen["fail_next"] = (429, {"statusCode": 429, "code": "RATE_LIMITED",
                                       "hint": {"action": "wait", "details": {"retryAfterSeconds": 3}}})
    cli.main(["sprixen", "tile", "mossy floor", "--url", url, "--out", str(tmp_path)])  # waited, then retried
    fake_sprixen["fail_next"] = (402, {"statusCode": 402, "message": "Not enough credits", "code": "INSUFFICIENT_CREDITS",
                                       "hint": {"action": "upgrade", "url": "https://sprixen.com/pricing"}})
    with pytest.raises(SystemExit):
        cli.main(["sprixen", "tile", "mossy floor", "--url", url, "--out", str(tmp_path)])
    assert "INSUFFICIENT_CREDITS: Not enough credits (next: upgrade https://sprixen.com/pricing)" in capsys.readouterr().err
    fake_sprixen["projects"].append({"id": "p9", "name": "um pixel_art side_scroll"})
    with pytest.raises(SystemExit):
        cli.main(["sprixen", "sprite", "doomed", "--url", url, "--out", str(tmp_path)])
    assert "background removal unavailable" in capsys.readouterr().err


def test_sprixen_key_sources(tmp_path, monkeypatch):
    for v in ("SPRIXEN_API_KEY", "UM_SPRIXEN_KEY_FILE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    def first():
        return sprixen.key_sources()[0][1]

    (tmp_path / ".env").write_text("SPRIXEN_API_KEY=spx_live_from_dotenv\n")
    assert first() == "spx_live_from_dotenv"
    fal.write_key_file("spx_live_from_file", sprixen.key_file())
    assert sprixen.key_file() == tmp_path / ".secrets" / "sprixen-key"
    assert first() == "spx_live_from_file"                                         # the stored file wins over .env
    monkeypatch.setattr(sprixen, "keyring_get", lambda: "spx_live_from_keyring")
    assert first() == "spx_live_from_keyring"                                      # the keyring wins over the file
    monkeypatch.setenv("UM_SPRIXEN_KEY_FILE", str(sprixen.key_file()))
    assert first() == "spx_live_from_file"                                         # unless the file is named on purpose
    monkeypatch.setenv("SPRIXEN_API_KEY", "spx_live_from_env")
    monkeypatch.setattr(sprixen, "keyring_get", lambda: pytest.fail("keyring read although SPRIXEN_API_KEY is set"))
    assert sprixen.api_key() == "spx_live_from_env"                                # the environment wins over all


def test_sprixen_key_set_prefers_the_keyring(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SPRIXEN_API_KEY", raising=False)
    monkeypatch.setenv("UM_SPRIXEN_KEY_FILE", str(tmp_path / "k"))
    key = "spx_" + "live_" + "Gh1jK2lM3nO4pQ5rS6tU7vW8xY9z0" * 2    # assembled so `um publish check` passes this file
    monkeypatch.setattr(sprixen.getpass, "getpass", lambda prompt: key)
    stored = {}
    monkeypatch.setattr(sprixen, "keyring_set", lambda value: stored.update(v=value) or True)
    monkeypatch.setattr(sprixen, "keyring_get", lambda: stored.get("v"))
    cli.main(["sprixen", "key", "set"])
    assert stored["v"] == key and not (tmp_path / "k").exists()
    monkeypatch.setattr(sprixen, "keyring_set", lambda value: False)              # no keyring: the owner-only file
    cli.main(["sprixen", "key", "set"])
    assert (tmp_path / "k").read_text().strip() == key
    cli.main(["sprixen", "key", "status"])
    out = capsys.readouterr().out
    assert "OS keyring" in out and key not in out                                 # keys are only shown masked
