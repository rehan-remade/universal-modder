"""Where `um fal` finds its key, and `um fal key`. Hermetic: no real keyring, no FAL_KEY from the caller's shell.

CI has no keyring (no secret-tool, no Secret Service), so the keyring is either patched or checked to be absent.
"""
from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from um import fal  # noqa: E402

KEY = "0123abcd-0000-1111-2222-333344445555:" + "f" * 32
POSIX = os.name == "posix"


@pytest.fixture
def clean(tmp_path, monkeypatch):
    """No key anywhere: own HOME, no env vars, no .env, no keyring, nothing cached."""
    for v in ("FAL_KEY", "FAL_KEY_FILE", "UM_FAL_KEY_FILE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fal, "_dotenv_files", lambda: [tmp_path / ".env"])
    monkeypatch.setattr(fal, "keyring_get", lambda: None)
    monkeypatch.setattr(fal, "keyring_set", lambda value: False)  # never write a test key into a real keyring
    monkeypatch.setattr(fal, "keyring_clear", lambda: False)
    monkeypatch.setattr(fal, "keyring_available", lambda: False)
    monkeypatch.setattr(fal, "_KEY_CACHE", None)
    return tmp_path


def test_precedence_env_keyring_file_dotenv(clean, monkeypatch, capsys):
    (clean / ".env").write_text('FAL_KEY="from-dotenv"\n')
    assert fal.key_sources() == [(f".env file {clean / '.env'}", "from-dotenv")]

    p = fal.write_key_file("from-file")
    assert p == clean / ".secrets" / "fal-key"
    monkeypatch.setattr(fal, "keyring_get", lambda: "from-keyring")
    assert [k for _, k in fal.key_sources()] == ["from-keyring", "from-file", "from-dotenv"]
    assert fal.fal_key() == "from-keyring"

    # FAL_KEY wins, and the keyring isn't even asked (a locked wallet would prompt; a hung one would stall)
    monkeypatch.setenv("FAL_KEY", "from-env\n")
    monkeypatch.setattr(fal, "_KEY_CACHE", None)
    monkeypatch.setattr(fal, "keyring_get", lambda: pytest.fail("keyring read although FAL_KEY is set"))
    assert fal.fal_key() == "from-env"

    # a file named by FAL_KEY_FILE (the old variable) comes before the keyring
    monkeypatch.delenv("FAL_KEY")
    monkeypatch.setenv("FAL_KEY_FILE", str(clean / "named"))
    fal.write_key_file("from-named")
    monkeypatch.setattr(fal, "keyring_get", lambda: "from-keyring")
    assert [k for _, k in fal.key_sources()] == ["from-named", "from-keyring", "from-dotenv"]

    # a plaintext source gets a hint only where a keyring exists to move it to
    monkeypatch.delenv("FAL_KEY_FILE")
    monkeypatch.setattr(fal, "keyring_get", lambda: None)
    monkeypatch.setattr(fal, "_KEY_CACHE", None)
    assert fal.fal_key() == "from-file" and "um fal key set" not in capsys.readouterr().err
    monkeypatch.setattr(fal, "keyring_available", lambda: True)
    monkeypatch.setattr(fal, "_KEY_CACHE", None)
    assert fal.fal_key() == "from-file" and "um fal key set" in capsys.readouterr().err

    p.unlink()
    (clean / ".env").unlink()
    monkeypatch.setattr(fal, "_KEY_CACHE", None)
    with pytest.raises(SystemExit):
        fal.fal_key()


def test_no_secret_tool_or_a_hung_one_is_not_an_error(monkeypatch):
    monkeypatch.setattr(fal.shutil, "which", lambda name: None)
    assert not fal.keyring_available()
    assert fal.keyring_get() is None and fal.keyring_set(KEY) is False and fal.keyring_clear() is False

    calls = []

    def hang(cmd, **kw):
        calls.append((cmd, kw))
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
    monkeypatch.setattr(fal.shutil, "which", lambda name: "/usr/bin/secret-tool")
    monkeypatch.setattr(fal.subprocess, "run", hang)
    assert fal.keyring_get() is None and fal.keyring_set(KEY) is False
    # the key goes to secret-tool on stdin, never on its command line (visible to every user in ps)
    store_cmd, store_kw = calls[-1]
    assert KEY not in store_cmd and store_kw["input"] == KEY


def run_key(action, **kw):
    fal.cmd_key(argparse.Namespace(action=action, **kw))


def test_set_without_keyring_writes_an_owner_only_file_and_status_masks(clean, monkeypatch, capsys):
    monkeypatch.setattr(fal.getpass, "getpass", lambda prompt="": KEY + "\n")
    run_key("set", from_file=None, file_only=False)
    p = clean / ".secrets" / "fal-key"
    assert p.read_text().strip() == KEY and "no OS keyring" in capsys.readouterr().out
    if POSIX:
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
        assert stat.S_IMODE(p.parent.stat().st_mode) == 0o700

    run_key("status")
    out = capsys.readouterr().out
    assert KEY not in out and fal.mask(KEY) in out and "active" in out

    run_key("clear", file=True)
    assert not p.exists()


@pytest.mark.skipif(not POSIX, reason="POSIX file modes")
def test_key_file_is_never_readable_by_others(clean):
    # an existing world-readable file is reset to 0600 before the key goes in, and the folder the user
    # named is left as it was (UM_FAL_KEY_FILE=~/fal-key must not chmod their home)
    shared = clean / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    f = shared / "fal-key"
    f.write_text("old\n")
    f.chmod(0o644)
    fal.write_key_file(KEY, f)
    assert stat.S_IMODE(f.stat().st_mode) == 0o600 and f.read_text().strip() == KEY
    assert stat.S_IMODE(shared.stat().st_mode) == 0o755


def test_set_refuses_when_the_keyring_will_not_store(clean, monkeypatch):
    monkeypatch.setattr(fal, "keyring_available", lambda: True)
    monkeypatch.setattr(fal, "keyring_set", lambda value: False)
    monkeypatch.setattr(fal.getpass, "getpass", lambda prompt="": KEY)
    with pytest.raises(SystemExit):
        run_key("set", from_file=None, file_only=False)
    assert not (clean / ".secrets" / "fal-key").exists()  # no silent plaintext fallback on a desktop

    stored = {}
    monkeypatch.setattr(fal, "keyring_set", lambda value: stored.setdefault("k", value) == value)
    monkeypatch.setattr(fal, "keyring_get", lambda: stored.get("k"))
    run_key("set", from_file=None, file_only=False)
    assert stored["k"] == KEY and not (clean / ".secrets" / "fal-key").exists()
