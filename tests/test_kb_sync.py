import http.client
import json
import sys
import threading
import time
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from um import cli, kb  # noqa: E402


class FakeResponse:
    def __init__(self, payload, error=None):
        self.payload = payload
        self.error = error

    def read(self):
        if self.error:
            raise self.error
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeNetwork:
    def __init__(self, files, *, delay=0, tree_error=None, file_error=None, read_error=None):
        self.files = files
        self.delay = delay
        self.tree_error = tree_error
        self.file_error = file_error
        self.read_error = read_error
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
            if self.file_error:
                raise self.file_error
            name = "knowledge/" + url.rsplit("/knowledge/", 1)[1]
            return FakeResponse(self.files[name], self.read_error)
        finally:
            with self.lock:
                self.active -= 1


def note(title):
    return f"---\ntitle: {title}\n---\n# {title}\n".encode()


def old_cache(tmp_path):
    root = tmp_path / "knowledge"
    (root / "games").mkdir(parents=True)
    (root / "games/xcom.md").write_text("---\ntitle: XCOM\ngame: XCOM 2\n---\nNative Vulkan route.\n", encoding="utf-8")
    (root / ".synced").write_text("0", encoding="utf-8")
    return root


def test_sync_is_bounded_parallel_and_counts_on_a_terminal(tmp_path, monkeypatch, capsys):
    files = {f"knowledge/games/game-{i}.md": note(f"Game {i}") for i in range(5)}
    files["knowledge/index.json"] = b"[]"
    network = FakeNetwork(files, delay=0.2)
    monkeypatch.setattr(kb, "cache_root", lambda: tmp_path / "knowledge")
    monkeypatch.setattr(kb.urllib.request, "urlopen", network.open)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    root = kb.sync(workers=2)
    assert network.peak == 2
    assert (root / "games/game-0.md").read_bytes() == files["knowledge/games/game-0.md"]
    progress = capsys.readouterr().err
    assert "1/6" in progress
    assert "6/6" in progress


def test_sync_through_a_pipe_says_one_line(tmp_path, monkeypatch, capsys):
    # an agent's tool call or a CI log keeps all of stderr: a counter would be one update per file
    network = FakeNetwork({f"knowledge/games/game-{i}.md": note(f"Game {i}") for i in range(3)})
    monkeypatch.setattr(kb, "cache_root", lambda: tmp_path / "knowledge")
    monkeypatch.setattr(kb.urllib.request, "urlopen", network.open)
    kb.sync()
    out, err = capsys.readouterr()
    assert err == "knowledge sync: 3 files...\n"
    assert out.startswith("synced 3 files")


def test_stale_cache_is_searchable_when_refresh_fails(tmp_path, monkeypatch, capsys):
    root = old_cache(tmp_path)
    network = FakeNetwork({}, tree_error=TimeoutError("stalled"))
    monkeypatch.setattr(kb, "cache_root", lambda: root)
    monkeypatch.setattr(kb.urllib.request, "urlopen", network.open)
    monkeypatch.setattr(kb, "local_root", lambda: None)
    monkeypatch.delenv("UM_KB", raising=False)
    found = kb.search(kb.resolve_root(remote=True), ["xcom"])
    assert [item["title"] for item in found] == ["XCOM"]
    assert "stale" in capsys.readouterr().err.lower()


def test_stale_cache_is_used_when_a_connection_drops_mid_file(tmp_path, monkeypatch, capsys):
    # http.client's IncompleteRead isn't an OSError: it went past the fallback as a traceback
    root = old_cache(tmp_path)
    network = FakeNetwork({"knowledge/games/new.md": note("New")}, read_error=http.client.IncompleteRead(b""))
    monkeypatch.setattr(kb, "cache_root", lambda: root)
    monkeypatch.setattr(kb.urllib.request, "urlopen", network.open)
    monkeypatch.delenv("UM_KB", raising=False)
    assert kb.resolve_root(remote=True) == root
    assert (root / "games/xcom.md").exists() and not (root / "games/new.md").exists()
    assert "stale" in capsys.readouterr().err.lower()


def test_stalled_download_stops_the_queue_and_keeps_the_cache(tmp_path, monkeypatch):
    # the rest of the queue would run first, each file taking its own timeout: minutes on a stalled network
    root = old_cache(tmp_path)
    files = {f"knowledge/games/game-{i}.md": note(f"Game {i}") for i in range(64)}
    network = FakeNetwork(files, delay=0.05, file_error=TimeoutError("stalled"))
    monkeypatch.setattr(kb, "cache_root", lambda: root)
    monkeypatch.setattr(kb.urllib.request, "urlopen", network.open)
    with pytest.raises(TimeoutError):
        kb.sync(quiet=True, workers=2)
    assert network.started < len(files)
    assert (root / "games/xcom.md").exists()
    assert not (tmp_path / "knowledge.tmp").exists()


def test_tree_without_knowledge_files_keeps_the_cache(tmp_path, monkeypatch):
    # a branch without knowledge/, say: the cache was replaced with nothing and marked fresh for a day
    root = old_cache(tmp_path)
    monkeypatch.setattr(kb, "cache_root", lambda: root)
    monkeypatch.setattr(kb.urllib.request, "urlopen", FakeNetwork({"README.md": b"x"}).open)
    with pytest.raises(ValueError, match="no knowledge files"):
        kb.sync(quiet=True)
    assert (root / "games/xcom.md").exists()
    assert (root / ".synced").read_text(encoding="utf-8") == "0"


def test_missing_cache_fails_quickly_without_partial_downloads(tmp_path, monkeypatch):
    calls = []

    def fail_tree(request, timeout):
        calls.append(timeout)
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(kb, "cache_root", lambda: tmp_path / "knowledge")
    monkeypatch.setattr(kb.urllib.request, "urlopen", fail_tree)
    with pytest.raises(OSError, match="offline"):
        kb.sync(quiet=True, timeout=3)
    assert calls == [3]
    assert not (tmp_path / "knowledge").exists()
    assert not (tmp_path / "knowledge.tmp").exists()


def test_search_says_it_is_syncing_and_keeps_stdout_clean(tmp_path, monkeypatch, capsys):
    # `um kb search --json` syncs through resolve_root: stderr explains the wait, stdout stays JSON
    network = FakeNetwork({"knowledge/index.json": b"[]"})
    monkeypatch.setattr(kb, "cache_root", lambda: tmp_path / "knowledge")
    monkeypatch.setattr(kb.urllib.request, "urlopen", network.open)
    monkeypatch.delenv("UM_KB", raising=False)
    kb.resolve_root(remote=True)
    out, err = capsys.readouterr()
    assert out == ""
    assert "knowledge sync" in err


def test_sync_command_fails_with_one_line(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(kb, "cache_root", lambda: tmp_path / "knowledge")
    monkeypatch.setattr(kb.urllib.request, "urlopen", FakeNetwork({}, tree_error=urllib.error.URLError("offline")).open)
    with pytest.raises(SystemExit) as e:
        cli.main(["kb", "sync"])
    assert e.value.code == 1
    assert "GitHub sync failed" in capsys.readouterr().err
