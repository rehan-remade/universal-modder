"""Adversarial security-boundary tests for production-readiness hardening."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import types
import urllib.error
import zipfile
from pathlib import Path

import pytest

from um import backup, comfy, fal, kb, publish, win


def _release_verifier_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_release_candidate.py"
    spec = importlib.util.spec_from_file_location("verify_release_candidate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _archive(path: Path, source: Path, files: dict[str, bytes], *, metadata: dict | None = None) -> Path:
    records = metadata or {
        name: {
            "size": len(data),
            "sha1": hashlib.sha1(data).hexdigest(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for name, data in files.items()
    }
    manifest = {"source": str(source), "created": "test", "note": "", "files": records}
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
        zf.writestr("_um_manifest.json", json.dumps(manifest))
    return path


@pytest.mark.parametrize("name", ["C:/escape.py", "pkg/./alias.py", "pkg//alias.py", "pkg/bad\x01.py"])
def test_release_verifier_rejects_noncanonical_member_names(name):
    assert not _release_verifier_module().safe_name(name)


@pytest.mark.parametrize("member", ["../outside.txt", "C:/windows.txt", r"..\\outside.txt"])
def test_backup_restore_rejects_unsafe_member_before_mutation(tmp_path, monkeypatch, member):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "home"))
    target = tmp_path / "target"
    target.mkdir()
    (target / "save.dat").write_text("original", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    archive = _archive(tmp_path / "hostile.zip", target, {member: b"hostile"})

    with pytest.raises(SystemExit):
        backup.restore("safe", to=str(target), snapshot=str(archive), yes=True)

    assert (target / "save.dat").read_text(encoding="utf-8") == "original"
    assert outside.read_text(encoding="utf-8") == "outside"


def test_backup_restore_verifies_hash_before_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "home"))
    target = tmp_path / "target"
    target.mkdir()
    (target / "save.dat").write_text("original", encoding="utf-8")
    archive = _archive(
        tmp_path / "bad-hash.zip",
        target,
        {"save.dat": b"replacement"},
        metadata={"save.dat": {"size": 11, "sha1": "0" * 40, "sha256": "0" * 64}},
    )

    with pytest.raises(SystemExit):
        backup.restore("safe", to=str(target), snapshot=str(archive), yes=True)

    assert (target / "save.dat").read_text(encoding="utf-8") == "original"


def test_backup_restore_uses_the_validated_open_archive_after_path_swap(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "home"))
    target = tmp_path / "target"
    target.mkdir()
    (target / "save.dat").write_bytes(b"current")
    approved = _archive(tmp_path / "snapshot.zip", target, {"save.dat": b"approved"})
    hostile = _archive(tmp_path / "hostile.zip", target, {"save.dat": b"ATTACKED"})

    def swap_during_pre_restore(*_args, **_kwargs):
        os.replace(hostile, approved)
        return tmp_path / "unused.zip"

    monkeypatch.setattr(backup, "create", swap_during_pre_restore)
    backup.restore("safe", to=str(target), snapshot=str(approved), yes=True)
    assert (target / "save.dat").read_bytes() == b"approved"


def test_backup_swap_recovery_restores_orphaned_rollback(tmp_path):
    target = tmp_path / "save"
    rollback = tmp_path / ".save.um-rollback-test"
    stage = tmp_path / ".save.um-restore-test"
    rollback.mkdir()
    stage.mkdir()
    (rollback / "old.dat").write_bytes(b"old")
    backup._write_swap_receipt(target, stage, rollback, "prepared")
    backup._recover_swap(target)
    assert (target / "old.dat").read_bytes() == b"old"
    assert not rollback.exists()
    assert not stage.exists()
    assert not backup._swap_receipt(target).exists()


def test_backup_name_cannot_escape_backup_root(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "home"))
    with pytest.raises(SystemExit):
        backup._root("../escape")
    assert not (tmp_path / "escape").exists()


def test_backup_creation_rejects_source_symlinks(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "home"))
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_text("private", encoding="utf-8")
    try:
        (source / "linked.txt").symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(SystemExit):
        backup.create(str(source), name="safe")


def test_fal_authenticated_requests_reject_non_fal_origin(monkeypatch):
    opened = []
    monkeypatch.setattr(fal, "fal_key", lambda: "test-only-placeholder")
    monkeypatch.setattr(fal.urllib.request, "urlopen", lambda req, timeout=None: opened.append(req))

    with pytest.raises(SystemExit):
        fal._req("GET", "https://attacker.invalid/status")

    assert opened == []


def test_fal_paid_post_is_not_retried_after_ambiguous_network_failure(monkeypatch):
    calls = []

    def fail(req, timeout=None):
        calls.append(req)
        raise urllib.error.URLError("ambiguous")

    monkeypatch.setattr(fal, "fal_key", lambda: "test-only-placeholder")
    monkeypatch.setattr(fal, "_urlopen", fail)
    monkeypatch.setattr(fal.time, "sleep", lambda _seconds: None)

    with pytest.raises(fal.AmbiguousSubmissionError):
        fal._req("POST", fal.QUEUE + "/fal-ai/test", {"prompt": "x"})

    assert len(calls) == 1


def test_fal_ambiguous_submission_writes_redacted_recovery_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(fal, "submit", lambda *_args, **_kwargs: (_ for _ in ()).throw(fal.AmbiguousSubmissionError("lost")))
    with pytest.raises(SystemExit):
        fal.run("fal-ai/test", {"prompt": "private input"})
    records = [json.loads(line) for line in (tmp_path / "home" / "fal-requests.jsonl").read_text().splitlines()]
    assert [record["state"] for record in records] == ["submission_attempt", "submission_ambiguous"]
    assert all("private input" not in json.dumps(record) for record in records)


def test_fal_download_rejects_untrusted_output_host_before_dns(monkeypatch):
    monkeypatch.delenv("UM_ALLOW_FAL_OUTPUT_HOSTS", raising=False)
    monkeypatch.setattr(fal.socket, "getaddrinfo", lambda *_args: pytest.fail("DNS should not run"))
    with pytest.raises(SystemExit):
        fal._validate_public_download_url("https://rebind.attacker.invalid/output.png")


def test_fal_authenticated_redirect_handler_rejects_cross_origin():
    request = fal.urllib.request.Request(fal.QUEUE + "/job", headers={"Authorization": "Key placeholder"})
    with pytest.raises(SystemExit):
        fal._FalRedirectHandler().redirect_request(
            request, None, 302, "Found", {}, fal.REST + "/job")  # type: ignore[arg-type]


def test_fal_output_name_cannot_escape_output_root(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(fal.urllib.request, "urlopen", lambda req, timeout=None: opened.append(req))

    with pytest.raises(SystemExit):
        fal.download_outputs({"image": {"url": "https://v3.fal.media/a.png"}}, tmp_path / "out", "../../escape")

    assert opened == []
    assert not (tmp_path / "escape.png").exists()


def test_powershell_process_filter_is_passed_as_data(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs.get("env", {})
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(win, "_check_platform", lambda: None)
    monkeypatch.setattr(win, "ps_exe", lambda: "powershell")
    monkeypatch.setattr(win, "is_wsl", lambda: False)
    monkeypatch.setattr(win.subprocess, "run", fake_run)
    hostile = "x'; Write-Output injected; #"

    assert win.processes(hostile) == []

    command = captured["command"]
    script = command[command.index("-Command") + 1]
    assert hostile not in script
    assert captured["env"]["UM_PROCESS_FILTER"] == hostile


def test_path_hook_shell_quotes_plugin_root(tmp_path):
    root = tmp_path / "um $(touch SHOULD_NOT_EXIST)"
    (root / "bin").mkdir(parents=True)
    launcher = root / "bin" / "um"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)
    env_file = tmp_path / "env.sh"
    hook = Path(__file__).resolve().parents[1] / "hooks" / "add-to-path.sh"

    subprocess.run(["bash", str(hook), str(root)], env={**os.environ, "CLAUDE_ENV_FILE": str(env_file)}, check=True)
    probe = subprocess.run(
        ["bash", "-c", 'source "$1"; printf "%s" "$PATH"', "bash", str(env_file)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    assert not (tmp_path / "SHOULD_NOT_EXIST").exists()
    assert probe.stdout.split(os.pathsep)[0] == str(root / "bin")


def test_publish_rejects_dotenv_variants(tmp_path):
    (tmp_path / "README.md").write_text("test", encoding="utf-8")
    (tmp_path / ".env.local").write_text("FAL_KEY=" + "A" * 32, encoding="utf-8")
    assert publish.check(str(tmp_path)) == 1


def test_publish_rejects_decompiled_code(tmp_path):
    (tmp_path / "README.md").write_text("test", encoding="utf-8")
    marker = "FUN" + "_00401000"
    (tmp_path / "source.c").write_text(f"// Decompiled with Example\nint {marker}();\n", encoding="utf-8")
    assert publish.check(str(tmp_path)) == 1


def test_publish_fails_closed_on_generated_environment_directories(tmp_path):
    (tmp_path / "README.md").write_text("candidate", encoding="utf-8")
    hidden = tmp_path / "venv"
    hidden.mkdir()
    (hidden / ".env").write_text("FAL_KEY=should-not-be-skipped", encoding="utf-8")
    assert publish.check(str(tmp_path)) == 1


def test_comfy_remote_requires_explicit_https_opt_in(monkeypatch):
    monkeypatch.delenv("UM_ALLOW_REMOTE_COMFYUI", raising=False)
    with pytest.raises(SystemExit):
        comfy.base_url("http://gpu.example.test:8188")
    with pytest.raises(SystemExit):
        comfy.base_url("https://gpu.example.test")
    monkeypatch.setenv("UM_ALLOW_REMOTE_COMFYUI", "1")
    assert comfy.base_url("https://gpu.example.test") == "https://gpu.example.test"


def test_kb_pr_rejects_pre_staged_files(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "secret.txt").write_text("private", encoding="utf-8")
    subprocess.run(["git", "add", "secret.txt"], cwd=tmp_path, check=True)
    with pytest.raises(SystemExit):
        kb._validate_pr_worktree(tmp_path, {"knowledge/new.md"})


@pytest.mark.parametrize("url", ["https://github.com/alice/universal-modder.git", "git@github.com:alice/universal-modder.git"])
def test_kb_remote_identity_is_exact(url):
    assert kb._github_remote(url) == ("alice", "universal-modder")
    kb._validate_fork_url(url, "alice")
    with pytest.raises(SystemExit):
        kb._validate_fork_url(url, "mallory")


@pytest.mark.parametrize("url", [
    "https://evil.example/github.com/alice/universal-modder.git",
    "https://github.com.evil.example/alice/universal-modder.git",
    "https://user@github.com/alice/universal-modder.git",
])
def test_kb_remote_parser_rejects_lookalike_github_urls(url):
    assert kb._github_remote(url) is None


def test_all_host_manifests_match_package_version():
    root = Path(__file__).resolve().parents[1]
    match = re.search(r'^version = "([^"]+)"$', (root / "pyproject.toml").read_text(), re.M)
    assert match
    version = match.group(1)
    assert version == __import__("um").__version__
    manifests = [root / "plugin.json", root / ".claude-plugin/plugin.json", root / ".codex-plugin/plugin.json",
                 root / ".cursor-plugin/plugin.json", root / "gemini-extension.json"]
    for manifest in manifests:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["name"] == "universal-modder"
        assert data["version"] == version


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("sha256sum") is None, reason="needs bash and sha256sum")
def test_example_installer_removes_only_owned_unchanged_files(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples" / "minecraft-gta5-passthrough" / "gta"
    fixture = tmp_path / "gta-tool"
    (fixture / "shaders").mkdir(parents=True)
    (fixture / "third_party").mkdir()
    shutil.copy2(source / "install.sh", fixture / "install.sh")
    shutil.copy2(source / "install_passthrough.py", fixture / "install_passthrough.py")
    shutil.copy2(source / "shaders" / "MCPassthrough.fx", fixture / "shaders" / "MCPassthrough.fx")
    (fixture / "third_party" / "ReShade.fxh").write_bytes(b"header-a")
    (fixture / "third_party" / "ReShadeUI.fxh").write_bytes(b"header-b")
    runtime = tmp_path / "runtime"
    build = tmp_path / "build"
    game = tmp_path / "game"
    runtime.mkdir()
    build.mkdir()
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    for name in ("ScriptHookV.dll", "dinput8.dll", "ReShade64.dll"):
        (runtime / name).write_bytes(name.encode())
    (build / "MCPassthrough.asi").write_bytes(b"asi")
    # An identical dependency that existed before installation is preserved and not claimed.
    shutil.copy2(runtime / "ScriptHookV.dll", game / "ScriptHookV.dll")
    env = {**os.environ, "GTA_DIR": str(game), "RUNTIME": str(runtime), "BUILD": str(build)}
    subprocess.run(["bash", str(fixture / "install.sh")], env=env, check=True, capture_output=True, text=True)
    manifest = game / ".universal-modder-mcpassthrough-owned"
    assert manifest.is_file()
    (game / "ReShade.ini").write_text("user changed this", encoding="utf-8")
    subprocess.run(["bash", str(fixture / "install.sh"), "--remove"], env=env, check=True, capture_output=True, text=True)
    assert (game / "ScriptHookV.dll").is_file()
    assert (game / "ReShade.ini").read_text() == "user changed this"
    assert not (game / "MCPassthrough.asi").exists()
    assert manifest.is_file()


def test_example_installer_rejects_symlinked_destination_ancestor(tmp_path):
    helper = (Path(__file__).resolve().parents[1] / "examples" / "minecraft-gta5-passthrough" / "gta"
              / "install_passthrough.py")
    game = tmp_path / "game"
    outside = tmp_path / "outside"
    game.mkdir()
    outside.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "shader.fx"
    source.write_bytes(b"shader")
    try:
        (game / "reshade-shaders").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    result = subprocess.run(
        [sys.executable, str(helper), "install", str(game), str(source), "reshade-shaders/Shaders/MCPassthrough.fx"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not any(outside.rglob("*"))


def test_example_uninstall_validates_entire_receipt_before_deleting(tmp_path):
    helper = (Path(__file__).resolve().parents[1] / "examples" / "minecraft-gta5-passthrough" / "gta"
              / "install_passthrough.py")
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    owned = game / "args.txt"
    owned.write_bytes(b"owned")
    receipt = game / ".universal-modder-mcpassthrough-owned"
    receipt.write_text(json.dumps({"entries": [
        {"path": "args.txt", "sha256": hashlib.sha256(b"owned").hexdigest()},
        {"path": "../unsafe", "sha256": "0" * 64},
    ]}), encoding="utf-8")
    result = subprocess.run([sys.executable, str(helper), "remove", str(game)], capture_output=True, text=True)
    assert result.returncode != 0
    assert owned.read_bytes() == b"owned"
