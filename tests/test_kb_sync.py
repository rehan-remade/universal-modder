import io
import json
import sys
import threading
import time
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from um import kb  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeNetwork:
    def __init__(self, files, *, delay=0, tree_error=None):
        self.files = files
        self.delay = delay
        self.tree_error = tree_error
        self.calls = []
        self.started = 0
        self.active = 0
        self.peak = 0
        self.lock = threading.Lock()

    def open(self, request, timeout):
        url = request.full_url
        self.calls.append(url)
        if "/git/trees/" in url:
            if self.tree_error:
                raise self.tree_error
            return FakeResponse(json.dumps({"tree": [
                {"path": path, "type": "blob"} for path in self.files
            ]}).encode())
        with self.lock:
            self.started += 1
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            name = "knowledge/" + url.rsplit("/knowledge/", 1)[1]
            return FakeResponse(self.files[name])
        finally:
            with self.lock:
                self.active -= 1


def note(title):
    return f"---\ntitle: {title}\n---\n# {title}\n".encode()


def test_sync_is_bounded_parallel_and_prints_progress(tmp_path, monkeypatch, capsys):
    files = {f"knowledge/games/game-{i}.md": note(f"Game {i}") for i in range(5)}
    files["knowledge/index.json"] = b"[]"
    network = FakeNetwork(files, delay=0.2)
    monkeypatch.setattr(kb, "cache_root", lambda: tmp_path / "knowledge")
    monkeypatch.setattr(kb.urllib.request, "urlopen", network.open)
    started = time.monotonic()
    root = kb.sync(workers=2)
    elapsed = time.monotonic() - started
    assert elapsed < 0.85, f"Serial downloads would take at least one second; took {elapsed:.2f}s"
    assert network.peak == 2
    assert (root / "games/game-0.md").read_bytes() == files["knowledge/games/game-0.md"]
    progress = capsys.readouterr().err
    assert "1/6" in progress
    assert "6/6" in progress


def test_stale_cache_is_searchable_when_refresh_fails(tmp_path, monkeypatch, capsys):
    root = tmp_path / "knowledge"
    (root / "games").mkdir(parents=True)
    (root / "games/xcom.md").write_text("---\ntitle: XCOM\ngame: XCOM 2\n---\nNative Vulkan route.\n", encoding="utf-8")
    (root / ".synced").write_text("0", encoding="utf-8")
    network = FakeNetwork({}, tree_error=TimeoutError("stalled"))
    monkeypatch.setattr(kb, "cache_root", lambda: root)
    monkeypatch.setattr(kb.urllib.request, "urlopen", network.open)
    monkeypatch.setattr(kb, "local_root", lambda: None)
    monkeypatch.delenv("UM_KB", raising=False)
    found = kb.search(kb.resolve_root(remote=True), ["xcom"])
    assert [item["title"] for item in found] == ["XCOM"]
    assert "stale" in capsys.readouterr().err.lower()


def test_missing_cache_fails_quickly_without_partial_downloads(tmp_path, monkeypatch):
    calls = []

    def fail_tree(request, timeout):
        calls.append(timeout)
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(kb, "cache_root", lambda: tmp_path / "knowledge")
    monkeypatch.setattr(kb.urllib.request, "urlopen", fail_tree)
    try:
        kb.sync(quiet=True, timeout=3)
    except OSError as error:
        assert "offline" in str(error)
    else:
        raise AssertionError("A failed first sync must not look successful")
    assert calls == [3]
    assert not (tmp_path / "knowledge").exists()
    assert not (tmp_path / "knowledge.tmp").exists()


def test_quiet_sync_has_no_progress(tmp_path, monkeypatch, capsys):
    network = FakeNetwork({"knowledge/index.json": b"[]"})
    monkeypatch.setattr(kb, "cache_root", lambda: tmp_path / "knowledge")
    monkeypatch.setattr(kb.urllib.request, "urlopen", network.open)
    kb.sync(quiet=True)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert not hasattr(sys.stdout, "isatty") or isinstance(captured.err, str)
