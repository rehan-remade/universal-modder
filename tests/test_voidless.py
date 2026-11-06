"""`um voidless` against a stand-in for the Voidless API: no key, no network, no credits."""
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

from um import cli, fal, voidless  # noqa: E402


@pytest.fixture(autouse=True)
def no_keyring(monkeypatch):
    """Never read or write the real desktop keyring, and start every test with no key cached."""
    monkeypatch.setattr(voidless, "keyring_get", lambda: None)
    monkeypatch.setattr(voidless, "keyring_set", lambda value: False)
    monkeypatch.setattr(voidless, "keyring_clear", lambda: False)
    monkeypatch.setattr(voidless, "keyring_available", lambda: False)
    monkeypatch.setattr(voidless, "_KEY_CACHE", None)


def png(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (w, h), (0, 0, 0, 0)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def fake_voidless(monkeypatch):
    """/api/generate/*, /api/assets/:id, /api/users/me, and the CDN the result keys point at."""
    state = {"posts": [], "auth": set(), "fail_next": None}
    files = {
        "/assets/u1/drone.png": png(64, 64),
        "/assets/u1/rot_0.png": png(64, 64),
        "/assets/u1/walk.png": png(256, 64),
    }

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
            if path in files:                                    # the CDN: static, no auth
                return self._send(files[path])
            self.state_auth()
            if path == "/api/users/me":
                return self._send({"id": 1, "username": "tester", "email": "t@example.com",
                                   "tier": "max", "subscribed": False, "credits": 420})
            if path == "/api/generate/multi-animation/presets":
                return self._send({"presets": [{"key": "platformer-character", "label": "Platformer character",
                                                "actions": ["idle", "run", "jump"]}]})
            if path == "/api/assets/115918":
                return self._send({"id": 115918, "name": "drone", "file": "assets/u1/drone.png",
                                   "meta_data": {"frames": [{"id": 0, "name": "rotations - 8-way",
                                                             "images": ["assets/u1/rot_0.png"]}]}})
            self._send({"error": {"message": "Not Found"}}, 404)

        def state_auth(self):
            state["auth"].add(self.headers.get("x-api-key"))

        def do_POST(self):
            path = urlparse(self.path).path
            self.state_auth()
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            state["posts"].append((path, body))
            if state["fail_next"]:
                code, payload = state["fail_next"]
                state["fail_next"] = None
                return self._send(payload, code)
            if path == "/api/generate/image":
                # Mirror the live contract: all of these are required and the real endpoint answers
                # 422 without them. referenceImage/styleImage have no default downstream either.
                required = {"prompt", "colours", "dimension", "size", "type", "model", "seed",
                            "referenceImage", "styleImage"}
                if missing := required - set(body):
                    return self._send({"error": {"message": f"missing {sorted(missing)}"}}, 422)
                return self._send({"assetId": 115918, "file": "assets/u1/drone.png", "seed": 7, "cost": 1})
            if path == "/api/generate/image-rotations":
                if not isinstance(body.get("id"), int):                 # asset ids are integers
                    return self._send({"error": {"message": "The given data is invalid."}}, 422)
                return self._send({"frames": [{"id": 0, "name": "rotations - 8-way",
                                               "images": ["assets/u1/rot_0.png"]}], "cost": 10})
            if path == "/api/generate/multi-animation":
                # It animates a list of images; {"id": …} is rejected as "attach at least one image".
                if not body.get("items"):
                    return self._send({"error": {"message": "Attach at least one image to animate."}}, 400)
                return self._send({"results": [{"assetId": 115918, "frames": [{"id": 1, "name": "walk",
                                                                             "images": ["assets/u1/walk.png"]}],
                                                "skipped": []}], "quality": "high", "cost": 24})
            self._send({"error": {"message": "Not Found"}}, 404)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("VOIDLESS_API_KEY", "void_test")
    monkeypatch.setattr(voidless.time, "sleep", lambda s: None)
    state["url"] = f"http://127.0.0.1:{srv.server_address[1]}"
    monkeypatch.setenv("VOIDLESS_API_URL", state["url"])      # a call without --url still stays on this machine
    monkeypatch.setenv("VOIDLESS_CDN_URL", state["url"])      # result keys resolve back to the same stand-in
    yield state
    srv.shutdown()


def test_voidless_sprite_rotate_then_animate(fake_voidless, tmp_path):
    out, url = tmp_path / "gen", fake_voidless["url"]
    cli.main(["voidless", "sprite", "a rusty scrap drone", "--url", url, "--out", str(out),
              "--facing", "right", "--model", "flux2-klein"])
    path, body = fake_voidless["posts"][0]
    assert path == "/api/generate/image"
    assert (body["prompt"], body["type"], body["model"]) == ("a rusty scrap drone", "character", "flux2-klein")
    assert body["options"]["facing"] == "right"   # forward|right only; left is a mirrored right
    assert Image.open(out / "a_rusty_scrap_drone.png").size == (64, 64)

    cli.main(["voidless", "rotate", "115918", "--url", url, "--out", str(out), "--name", "drone"])
    assert fake_voidless["posts"][-1] == ("/api/generate/image-rotations", {"id": 115918, "referenceFile": ""})

    cli.main(["voidless", "animate", "115918", "--preset", "platformer-character", "--url", url, "--out", str(out),
              "--name", "drone", "--hold-facing"])
    path, body = fake_voidless["posts"][-1]
    assert path == "/api/generate/multi-animation"
    assert body["items"] == [{"assetId": 115918}] and "quality" not in body   # a list, never a bare id
    # flipFacings defaults on: the left-side clips are mirrored from the right at half the price.
    assert (body["preset"], body["holdFacing"], body["flipFacings"], body["autoFlip"]) == ("platformer-character", True, True, False)
    assert Image.open(out / "drone_walk.png").size == (256, 64)

    rec = [json.loads(x) for x in (out / "voidless_manifest.jsonl").read_text().splitlines()]
    assert [r["cmd"] for r in rec] == ["sprite", "rotate", "animate"]
    assert rec[0]["asset"] == 115918 and rec[0]["seed"] == 7 and rec[0]["size"] == 512
    assert rec[-1]["hold_facing"] is True
    assert fake_voidless["auth"] == {"void_test"}             # the CDN is anonymous, the API is not


def test_voidless_credits_presets_asset_and_errors(fake_voidless, tmp_path, capsys):
    url = fake_voidless["url"]
    cli.main(["voidless", "credits", "--url", url])
    out = capsys.readouterr().out
    assert "420" in out and "max" in out            # tier, not "plan": /users/me has no plan field
    cli.main(["voidless", "presets", "--url", url])
    out = capsys.readouterr().out
    # the key is what `animate --preset` takes; the label and actions are there to choose by
    assert "platformer-character" in out and "idle, run, jump" in out
    cli.main(["voidless", "asset", "115918", "--url", url, "--urls"])
    out = capsys.readouterr().out
    assert "rotations - 8-way" in out and "/assets/u1/rot_0.png" in out

    # animate needs something to animate
    with pytest.raises(SystemExit):
        cli.main(["voidless", "animate", "115918", "--url", url, "--out", str(tmp_path)])
    assert "--preset" in capsys.readouterr().err

    # 429 is waited out and retried; the call then succeeds
    fake_voidless["fail_next"] = (429, {"error": {"message": "Too many requests"}})
    cli.main(["voidless", "sprite", "retried", "--url", url, "--out", str(tmp_path)])
    assert "retrying" in capsys.readouterr().err

    # a real failure stops, with the server's own message
    fake_voidless["fail_next"] = (402, {"error": {"message": "Not enough credits"}})
    with pytest.raises(SystemExit):
        cli.main(["voidless", "sprite", "doomed", "--url", url, "--out", str(tmp_path)])
    assert "HTTP 402: Not enough credits" in capsys.readouterr().err


def test_voidless_key_sources(tmp_path, monkeypatch):
    for v in ("VOIDLESS_API_KEY", "UM_VOIDLESS_KEY_FILE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    def first():
        return voidless.key_sources()[0][1]

    (tmp_path / ".env").write_text("VOIDLESS_API_KEY=void_from_dotenv\n")
    assert first() == "void_from_dotenv"
    fal.write_key_file("void_from_file", voidless.key_file())
    assert voidless.key_file() == tmp_path / ".secrets" / "voidless-key"
    assert first() == "void_from_file"                                         # the stored file wins over .env
    monkeypatch.setattr(voidless, "keyring_get", lambda: "void_from_keyring")
    assert first() == "void_from_keyring"                                      # the keyring wins over the file
    monkeypatch.setenv("UM_VOIDLESS_KEY_FILE", str(voidless.key_file()))
    assert first() == "void_from_file"                                         # unless the file is named on purpose
    monkeypatch.setenv("VOIDLESS_API_KEY", "void_from_env")
    monkeypatch.setattr(voidless, "keyring_get", lambda: pytest.fail("keyring read although VOIDLESS_API_KEY is set"))
    assert voidless.api_key() == "void_from_env"                               # the environment wins over all


def test_voidless_key_set_prefers_the_keyring(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("VOIDLESS_API_KEY", raising=False)
    monkeypatch.setenv("UM_VOIDLESS_KEY_FILE", str(tmp_path / "k"))
    key = "void_" + "Gh1jK2lM3nO4pQ5rS6tU7vW8xY9z0" * 2        # assembled so `um publish check` passes this file
    monkeypatch.setattr(voidless.getpass, "getpass", lambda prompt: key)
    stored = {}
    monkeypatch.setattr(voidless, "keyring_set", lambda value: stored.update(v=value) or True)
    monkeypatch.setattr(voidless, "keyring_get", lambda: stored.get("v"))
    cli.main(["voidless", "key", "set"])
    assert stored["v"] == key and not (tmp_path / "k").exists()
    monkeypatch.setattr(voidless, "keyring_set", lambda value: False)          # no keyring: the owner-only file
    cli.main(["voidless", "key", "set"])
    assert (tmp_path / "k").read_text().strip() == key
    cli.main(["voidless", "key", "status"])
    out = capsys.readouterr().out
    assert "OS keyring" in out and key not in out                              # keys are only shown masked


def test_voidless_fetch_redownloads_without_generating(fake_voidless, tmp_path, capsys):
    """Generation and download are separate; only the first costs credits.

    A download cut short used to leave frames paid for and unreachable, so `fetch` asks the API for
    them again and posts nothing.
    """
    url = fake_voidless["url"]
    cli.main(["voidless", "fetch", "115918", "--url", url, "--out", str(tmp_path), "--name", "drone"])
    out = capsys.readouterr().out
    assert "no credits spent" in out
    assert (tmp_path / "drone.png").exists()                      # the base image
    assert (tmp_path / "drone_rotations_8way.png").exists() or any(tmp_path.glob("drone_rotations*"))
    assert not [p for p, _ in fake_voidless["posts"]]             # nothing was POSTed, so nothing was charged


def test_voidless_tileset_always_uses_the_tileset_model(fake_voidless, tmp_path, capsys):
    """A tileset is drawn by gpt-image-2.5 whatever --model says, because the server replaces it.

    Silently sending the cheap model would make the call cost five times what the flag implies, so
    the swap is announced and the request carries the model that will actually be used.
    """
    cli.main(["voidless", "sprite", "mossy cobblestone", "--type", "tileset", "--model", "flux2-klein",
              "--url", fake_voidless["url"], "--out", str(tmp_path), "--name", "floor"])
    assert "always generated with gpt-image-2.5" in capsys.readouterr().err
    _, body = fake_voidless["posts"][-1]
    assert body["model"] == "gpt-image-2.5"
    rec = [json.loads(x) for x in (tmp_path / "voidless_manifest.jsonl").read_text().splitlines()]
    assert rec[-1]["model"] == "gpt-image-2.5"          # the manifest records what was charged for


def test_voidless_animate_one_frame_image_and_quality(fake_voidless, tmp_path):
    """--frame-id/--image-index pick one image of a frame (e.g. a facing of the 8-way rotation), sent as
    frameIndex/imageIndex like the vendor's MCP server; --quality is sent only when given."""
    cli.main(["voidless", "animate", "115918", "--preset", "topdown-walk", "--frame-id", "3", "--image-index", "2",
              "--quality", "ultra", "--url", fake_voidless["url"], "--out", str(tmp_path)])
    _, body = fake_voidless["posts"][-1]
    assert body["items"] == [{"assetId": 115918, "frameIndex": 3, "imageIndex": 2}] and body["quality"] == "ultra"


def test_voidless_post_is_not_retried_after_a_gateway_error(fake_voidless, tmp_path, capsys):
    """A 502/503/504 on a generation POST may come from a gateway while the job still finishes and is charged."""
    fake_voidless["fail_next"] = (504, {"error": {"message": "Gateway Timeout"}})
    with pytest.raises(SystemExit):
        cli.main(["voidless", "rotate", "115918", "--url", fake_voidless["url"], "--out", str(tmp_path)])
    err = capsys.readouterr().err
    assert "retrying" not in err and "may still finish" in err
    assert len(fake_voidless["posts"]) == 1


def test_voidless_read_only_commands_make_no_folder(fake_voidless, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli.main(["voidless", "credits", "--url", fake_voidless["url"]])
    cli.main(["voidless", "asset", "115918", "--url", fake_voidless["url"]])
    assert not (tmp_path / "assets").exists()
