"""Adversarial security-boundary tests for production-readiness hardening."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import time
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


def _installer_module():
    path = (Path(__file__).resolve().parents[1] / "examples" / "minecraft-gta5-passthrough" / "gta"
            / "install_passthrough.py")
    spec = importlib.util.spec_from_file_location("install_passthrough", path)
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


def test_fal_paid_post_http_5xx_is_ambiguous(monkeypatch):
    def fail(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 503, "unavailable", {}, None)

    monkeypatch.setattr(fal, "fal_key", lambda: "test-only-placeholder")
    monkeypatch.setattr(fal, "_urlopen", fail)
    with pytest.raises(fal.AmbiguousSubmissionError):
        fal._req("POST", fal.QUEUE + "/fal-ai/test", {"prompt": "x"})


def test_fal_paid_post_socket_timeout_is_ambiguous(monkeypatch):
    monkeypatch.setattr(fal, "fal_key", lambda: "test-only-placeholder")
    monkeypatch.setattr(fal, "_urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("timed out")))
    with pytest.raises(fal.AmbiguousSubmissionError):
        fal._req("POST", fal.QUEUE + "/fal-ai/test", {"prompt": "x"})


def test_fal_provider_failure_records_terminal_lifecycle_state(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(fal, "submit", lambda *_args, **_kwargs: {"request_id": "req-1"})
    monkeypatch.setattr(fal, "_req", lambda *_args, **_kwargs: {"status": "COMPLETED", "error": "failed"})
    with pytest.raises(SystemExit):
        fal.run("fal-ai/test", {}, quiet=True)
    records = [json.loads(line) for line in (tmp_path / "home" / "fal-requests.jsonl").read_text().splitlines()]
    assert records[-1]["state"] == "provider_failed"


def test_fal_explicit_failed_status_is_terminal_provider_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(fal, "submit", lambda *_args, **_kwargs: {"request_id": "req-failed"})
    monkeypatch.setattr(fal, "_req", lambda *_args, **_kwargs: {"status": "FAILED", "error": "rejected"})
    with pytest.raises(SystemExit):
        fal.run("fal-ai/test", {}, quiet=True, timeout=0)
    records = [json.loads(line) for line in (tmp_path / "home" / "fal-requests.jsonl").read_text().splitlines()]
    assert [record["state"] for record in records] == ["submission_attempt", "submitted", "provider_failed"]


def test_fal_result_records_reconciliation_outcome(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(fal, "_req", lambda *_args, **_kwargs: {"output": "ok"})
    monkeypatch.setattr(fal, "download_outputs", lambda *_args, **_kwargs: [])
    args = types.SimpleNamespace(recipe="result", endpoint="fal-ai/test", request_id="req-1",
                                 out=str(tmp_path / "out"), name=None)
    fal.cmd(args)
    records = [json.loads(line) for line in (tmp_path / "home" / "fal-requests.jsonl").read_text().splitlines()]
    assert records[-1]["state"] == "reconciled_completed"
    assert records[-1]["request_id"] == "req-1"


@pytest.mark.parametrize(("payload", "state", "raises"), [
    ({"status": "IN_QUEUE"}, "reconciled_pending", False),
    ({"status": "COMPLETED", "error": "failed"}, "reconciled_provider_failed", True),
    ({"status": "CANCELED"}, "reconciled_provider_failed", True),
])
def test_fal_result_classifies_non_success_outcomes(tmp_path, monkeypatch, payload, state, raises):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(fal, "_req", lambda *_args, **_kwargs: payload)
    monkeypatch.setattr(fal, "download_outputs", lambda *_args, **_kwargs: pytest.fail("must not download"))
    args = types.SimpleNamespace(recipe="result", endpoint="fal-ai/test", request_id="req-1",
                                 out=str(tmp_path / "out"), name=None)
    if raises:
        with pytest.raises(SystemExit):
            fal.cmd(args)
    else:
        fal.cmd(args)
    records = [json.loads(line) for line in (tmp_path / "home" / "fal-requests.jsonl").read_text().splitlines()]
    assert [record["state"] for record in records] == [state]


def test_fal_pinned_connection_uses_validated_ip_and_original_tls_name(monkeypatch):
    seen = {}

    class Context:
        def wrap_socket(self, sock, server_hostname=None):
            seen["sni"] = server_hostname
            return sock

    raw = object()

    def connect(address, *_args):
        seen["address"] = address
        return raw

    monkeypatch.setattr(fal.socket, "create_connection", connect)
    connection = fal._PinnedHTTPSConnection("v3.fal.media", "8.8.8.8", timeout=1)
    connection._context = Context()
    connection.connect()
    assert seen == {"address": ("8.8.8.8", 443), "sni": "v3.fal.media"}


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


def test_windows_tree_kill_timeout_falls_back_to_direct_kill(monkeypatch):
    class Process:
        pid = 1234

        def __init__(self):
            self.killed = False
            self.waited = 0

        def poll(self):
            return None

        def kill(self):
            self.killed = True

        def wait(self, _timeout=None):
            self.waited += 1
            return 0

    process = Process()
    monkeypatch.setattr(win.os, "name", "nt")
    monkeypatch.setattr(win.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        subprocess.TimeoutExpired("taskkill", 1)))
    win._stop_child(process, timeout=1)
    assert process.killed
    assert process.waited == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group regression")
def test_helper_timeout_stops_descendants_after_successful_parent_exit():
    code = ("import subprocess,sys; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            "print(p.pid,file=sys.stderr,flush=True)")
    process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    assert process.stderr is not None
    descendant = int(process.stderr.readline().strip())
    process.wait(timeout=5)
    with pytest.raises(TimeoutError):
        win._readline_bounded(process, 0.2, "probe")
    with pytest.raises(ProcessLookupError):
        os.kill(descendant, 0)


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
    assignment = "FAL" + "_KEY=should-not-be-skipped"
    (hidden / ".env").write_text(assignment, encoding="utf-8")
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


def test_kb_existing_branch_is_never_deleted_by_collision_preflight(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    (tmp_path / "tracked").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "tracked"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "branch", "kb/collision"], cwd=tmp_path, check=True)
    with pytest.raises(SystemExit):
        kb._ensure_branch_absent(tmp_path, "kb/collision")
    branches = subprocess.check_output(["git", "branch", "--format=%(refname:short)"], cwd=tmp_path, text=True).splitlines()
    assert "kb/collision" in branches


def test_kb_cleanup_never_deletes_a_branch_moved_by_another_actor(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    (tmp_path / "tracked").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "tracked"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    subprocess.run(["git", "branch", "kb/race"], cwd=tmp_path, check=True)
    owned = subprocess.check_output(["git", "rev-parse", "kb/race"], cwd=tmp_path, text=True).strip()
    (tmp_path / "tracked").write_text("caller", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "caller"], cwd=tmp_path, check=True)
    caller = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    original_run = kb.subprocess.run

    def race(command, *args, **kwargs):
        if command[:3] == ["git", "update-ref", "-d"]:
            original_run(["git", "update-ref", "refs/heads/kb/race", caller], cwd=tmp_path, check=True)
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(kb.subprocess, "run", race)
    assert not kb._delete_branch_if_owned(tmp_path, "kb/race", owned)
    monkeypatch.setattr(kb.subprocess, "run", original_run)
    assert subprocess.check_output(["git", "rev-parse", "kb/race"], cwd=tmp_path, text=True).strip() == caller


def test_ci_generates_coverage_xml_and_scans_clean_export():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    assert "--cov-report=xml" in workflow
    assert "um publish check ." not in workflow
    assert "um publish check \"$RUNNER_TEMP/candidate\"" in workflow
    assert 'package_root="$RUNNER_TEMP/um-package"' in workflow
    assert "mkdir source-a source-b dist-a dist-b" not in workflow


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


def test_example_uninstall_validates_all_ancestors_before_any_deletion(tmp_path):
    helper = _installer_module()
    game = tmp_path / "game"
    outside = tmp_path / "outside"
    game.mkdir()
    outside.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    args = game / "args.txt"
    args.write_bytes(b"owned")
    nested_digest = hashlib.sha256(b"nested").hexdigest()
    receipt = game / helper.MANIFEST_NAME
    receipt.write_text(json.dumps({"format": 1, "state": "installed", "entries": [
        {"path": "reshade-shaders/Shaders/MCPassthrough.fx", "sha256": nested_digest},
        {"path": "args.txt", "sha256": hashlib.sha256(b"owned").hexdigest()},
    ]}), encoding="utf-8")
    os.link(receipt, game / helper.MANIFEST_MARKER_NAME)
    (game / "reshade-shaders").symlink_to(outside, target_is_directory=True)
    with pytest.raises(SystemExit):
        helper.remove(game)
    assert args.read_bytes() == b"owned"


def test_example_installer_does_not_clobber_file_created_after_preflight(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    original_write = helper.write_json_atomic

    raced = False

    def race(path, payload, **kwargs):
        nonlocal raced
        original_write(path, payload, **kwargs)
        if not raced:
            raced = True
            (game / "args.txt").write_bytes(b"user")

    monkeypatch.setattr(helper, "write_json_atomic", race)
    with pytest.raises(SystemExit):
        helper.install(game, [str(source), "args.txt"])
    assert (game / "args.txt").read_bytes() == b"user"


def test_example_installer_does_not_clobber_manifest_created_during_install(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    original_write = helper.write_json_atomic

    def race(path, payload, **kwargs):
        if path.name == helper.MANIFEST_NAME and not path.exists():
            path.write_text('{"caller": true}\n', encoding="utf-8")
        return original_write(path, payload, **kwargs)

    monkeypatch.setattr(helper, "write_json_atomic", race)
    with pytest.raises(SystemExit):
        helper.install(game, [str(source), "args.txt"])
    assert json.loads((game / helper.MANIFEST_NAME).read_text()) == {"caller": True}
    assert not (game / "args.txt").exists()


def test_example_installer_matching_concurrent_manifest_is_not_its_commit(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    original_write = helper.write_json_atomic

    def race(path, payload, **kwargs):
        if path.name == helper.MANIFEST_NAME and not path.exists():
            path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        return original_write(path, payload, **kwargs)

    monkeypatch.setattr(helper, "write_json_atomic", race)
    with pytest.raises(SystemExit):
        helper.install(game, [str(source), "args.txt"])
    assert (game / helper.MANIFEST_NAME).exists()
    assert not (game / "args.txt").exists()
    assert not (game / helper.JOURNAL_NAME).exists()


def test_example_installer_ancestor_swap_cannot_write_outside_root(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    outside = tmp_path / "outside"
    source = tmp_path / "shader.fx"
    game.mkdir()
    outside.mkdir()
    (outside / "Shaders").mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    (game / "reshade-shaders" / "Shaders").mkdir(parents=True)
    source.write_bytes(b"installer-owned-bytes")
    original_open = helper.os.open
    swapped = False

    def racing_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if not swapped and ".MCPassthrough.fx.um-part-" in str(path):
            swapped = True
            (game / "reshade-shaders").rename(game / "reshade-shaders-original")
            (game / "reshade-shaders").symlink_to(outside, target_is_directory=True)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(helper.os, "open", racing_open)
    with pytest.raises(BaseException):
        helper.install(game, [str(source), "reshade-shaders/Shaders/MCPassthrough.fx"])
    assert not any(path.is_file() for path in outside.rglob("*"))


def test_example_installer_recovers_interruption_after_target_publication(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    original_publish = helper._publish_target
    raised = False

    def interrupt(*args, **kwargs):
        nonlocal raised
        original_publish(*args, **kwargs)
        if not raised:
            raised = True
            raise RuntimeError("interrupted after target publication")

    monkeypatch.setattr(helper, "_publish_target", interrupt)
    with pytest.raises(RuntimeError):
        helper.install(game, [str(source), "args.txt"])
    monkeypatch.setattr(helper, "_publish_target", original_publish)
    helper.recover(game, game / helper.JOURNAL_NAME)
    assert not (game / "args.txt").exists()
    assert not (game / helper.JOURNAL_NAME).exists()


def test_example_installer_journals_stage_identity_before_stage_creation(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    events = []
    original_write = helper.write_json_atomic
    original_open = helper.os.open

    def observe_write(path, payload, **kwargs):
        if path.name == helper.JOURNAL_NAME and payload.get("entries"):
            events.append("journal")
        return original_write(path, payload, **kwargs)

    def observe_open(path, *args, **kwargs):
        if ".um-part-" in str(path):
            events.append("stage")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(helper, "write_json_atomic", observe_write)
    monkeypatch.setattr(helper.os, "open", observe_open)
    helper.install(game, [str(source), "args.txt"])
    assert events[:2] == ["journal", "stage"]


def test_example_recovery_retains_journal_for_tampered_committed_stage(tmp_path):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    digest = hashlib.sha256(b"installed").hexdigest()
    nonce = "a" * 16
    entry = {"path": "args.txt", "sha256": digest, "nonce": nonce}
    journal = game / helper.JOURNAL_NAME
    manifest = game / helper.MANIFEST_NAME
    journal.write_text(json.dumps({"format": 1, "state": "installing", "entries": [entry]}), encoding="utf-8")
    manifest.write_text(json.dumps({"format": 1, "state": "installed",
                                    "entries": [{"path": "args.txt", "sha256": digest}]}), encoding="utf-8")
    os.link(manifest, game / helper.MANIFEST_MARKER_NAME)
    (game / f".args.txt.um-part-{nonce}").write_bytes(b"tampered")
    with pytest.raises(SystemExit):
        helper.recover(game, journal)
    assert journal.exists()
    assert manifest.exists()
    assert (game / f".args.txt.um-part-{nonce}").exists()


def test_example_remove_recovers_crash_after_quarantine_rename(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    helper.install(game, [str(source), "args.txt"])
    original_unlink = helper._parent_unlink
    interrupted = False

    def interrupt_quarantine_unlink(parent, name):
        nonlocal interrupted
        if not interrupted and ".um-remove-" in name:
            interrupted = True
            raise KeyboardInterrupt("crash after quarantine rename")
        original_unlink(parent, name)

    monkeypatch.setattr(helper, "_parent_unlink", interrupt_quarantine_unlink)
    with pytest.raises(KeyboardInterrupt):
        helper.remove(game)
    monkeypatch.setattr(helper, "_parent_unlink", original_unlink)
    helper.remove(game)
    assert not (game / "args.txt").exists()
    assert not (game / helper.MANIFEST_NAME).exists()
    assert not (game / helper.MANIFEST_MARKER_NAME).exists()
    assert not list(game.glob("*.um-remove-*"))
    assert not list(game.glob(".*.um-remove-*"))


def test_example_recovery_removes_no_manifest_temp_hardlink(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    original_unlink = Path.unlink
    interrupted = False

    def interrupt_temp_unlink(path, *args, **kwargs):
        nonlocal interrupted
        if (not interrupted and f".{helper.MANIFEST_NAME}.tmp-" in path.name
                and (game / helper.MANIFEST_NAME).exists()):
            interrupted = True
            raise KeyboardInterrupt("crash before manifest temp unlink")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", interrupt_temp_unlink)
    try:
        helper.install(game, [str(source), "args.txt"])
    except KeyboardInterrupt:
        pass
    monkeypatch.setattr(Path, "unlink", original_unlink)
    helper.recover(game, game / helper.JOURNAL_NAME)
    assert not list(game.glob(f".{helper.MANIFEST_NAME}.tmp-*"))


def test_example_installer_pins_root_identity_across_path_replacement(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    moved = tmp_path / "game-original"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    original_write = helper.write_json_atomic
    swapped = False

    def replace_root_after_journal(path, payload, **kwargs):
        nonlocal swapped
        result = original_write(path, payload, **kwargs)
        if path.name == helper.JOURNAL_NAME and not swapped:
            swapped = True
            game.rename(moved)
            game.mkdir()
            (game / "GTA5.exe").write_bytes(b"replacement")
            with pytest.raises(SystemExit, match="another passthrough"):
                helper.remove(game)
        return result

    monkeypatch.setattr(helper, "write_json_atomic", replace_root_after_journal)
    with pytest.raises(SystemExit, match="identity changed"):
        helper.install(game, [str(source), "args.txt"])
    assert (moved / "args.txt").read_bytes() == b"installer"
    assert (moved / helper.MANIFEST_NAME).exists()
    assert not (game / "args.txt").exists()
    assert not (game / helper.MANIFEST_NAME).exists()


def test_example_installer_manifest_marker_lifecycle(tmp_path):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    helper.install(game, [str(source), "args.txt"])
    manifest = game / helper.MANIFEST_NAME
    marker = game / helper.MANIFEST_MARKER_NAME
    assert os.path.samefile(manifest, marker)
    helper.remove(game)
    assert not manifest.exists()
    assert not marker.exists()
    assert not (game / "args.txt").exists()


def test_example_installer_native_windows_fails_closed_with_wsl_guidance(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    monkeypatch.setattr(helper.os, "name", "nt")
    with pytest.raises(SystemExit, match="WSL"):
        helper.install(game, [])
    with pytest.raises(SystemExit, match="WSL"):
        helper._open_parent_fd(game, "args.txt")


def test_example_installer_process_lock_is_released_after_sigkill(tmp_path):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    ready = tmp_path / "ready"
    assert helper.__file__ is not None
    helper_path = Path(helper.__file__)
    code = (
        "import importlib.util,time\n"
        "from pathlib import Path\n"
        f"s=importlib.util.spec_from_file_location('h',{str(helper_path)!r});"
        "h=importlib.util.module_from_spec(s);s.loader.exec_module(h)\n"
        f"def hold(root,pairs): Path({str(ready)!r}).write_text('ready'); time.sleep(60)\n"
        f"h._install=hold;h.install(Path({str(game)!r}),[])\n"
    )
    child = subprocess.Popen([sys.executable, "-c", code])
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        os.kill(child.pid, signal.SIGKILL)
        child.wait(timeout=5)
        helper.recover(game, game / helper.JOURNAL_NAME)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_example_installer_rollback_preserves_leaf_replaced_after_validation(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    target = game / "args.txt"
    target.write_bytes(b"owned")
    entry = {"path": "args.txt", "sha256": hashlib.sha256(b"owned").hexdigest()}
    original = helper._parent_rename
    swapped = False

    def race(parent, name, quarantine):
        nonlocal swapped
        if not swapped and name == "args.txt" and isinstance(parent, int):
            swapped = True
            os.rename("args.txt", "owned-before-race.txt", src_dir_fd=parent, dst_dir_fd=parent)
            fd = os.open("args.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent)
            os.write(fd, b"user-concurrent-data")
            os.close(fd)
        original(parent, name, quarantine)

    monkeypatch.setattr(helper, "_parent_rename", race)
    assert helper.rollback(game, [entry]) is False
    assert target.read_bytes() == b"user-concurrent-data"


def test_example_recovery_rejects_matching_foreign_manifest_inode(tmp_path):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    payload = b"owned"
    digest = hashlib.sha256(payload).hexdigest()
    nonce = "a" * 16
    target = game / "args.txt"
    target.write_bytes(payload)
    os.link(target, game / f".args.txt.um-part-{nonce}")
    public = {"format": 1, "state": "installed", "entries": [{"path": "args.txt", "sha256": digest}]}
    journal = {"format": 1, "state": "installing", "entries": [
        {"path": "args.txt", "sha256": digest, "nonce": nonce},
    ]}
    journal_path = game / helper.JOURNAL_NAME
    journal_path.write_text(json.dumps(journal), encoding="utf-8")
    (game / helper.MANIFEST_NAME).write_text(json.dumps(public), encoding="utf-8")
    marker = game / helper.MANIFEST_MARKER_NAME
    marker.write_text(json.dumps(public), encoding="utf-8")
    with pytest.raises(SystemExit, match="not bound"):
        helper.recover(game, journal_path)
    assert journal_path.exists()
    assert (game / f".args.txt.um-part-{nonce}").exists()


def test_example_installer_blocks_concurrent_recovery_during_install(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    original_write = helper.write_json_atomic
    attempted = False

    def race(path, payload, **kwargs):
        nonlocal attempted
        if path.name == helper.MANIFEST_NAME and not attempted:
            attempted = True
            with pytest.raises(SystemExit):
                helper.recover(game, game / helper.JOURNAL_NAME)
        return original_write(path, payload, **kwargs)

    monkeypatch.setattr(helper, "write_json_atomic", race)
    helper.install(game, [str(source), "args.txt"])
    assert attempted
    assert (game / "args.txt").read_bytes() == b"installer"
    assert (game / helper.MANIFEST_NAME).exists()
    assert not (game / helper.JOURNAL_NAME).exists()


def test_example_installer_drops_own_manifest_if_committed_target_disappears(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    manifest = game / helper.MANIFEST_NAME
    target = game / "args.txt"
    original_fsync = helper._fsync_dir
    injected = False

    def fail_after_removing_target(path):
        nonlocal injected
        if not injected and manifest.exists() and target.exists():
            injected = True
            target.unlink()
            raise OSError("injected target loss after manifest publication")
        return original_fsync(path)

    monkeypatch.setattr(helper, "_fsync_dir", fail_after_removing_target)
    with pytest.raises(OSError):
        helper.install(game, [str(source), "args.txt"])
    assert not manifest.exists()


def test_example_installer_preserves_committed_install_when_manifest_fsync_fails(tmp_path, monkeypatch):
    helper = _installer_module()
    game = tmp_path / "game"
    game.mkdir()
    (game / "GTA5.exe").write_bytes(b"game")
    source = tmp_path / "args-source.txt"
    source.write_bytes(b"installer")
    manifest = game / helper.MANIFEST_NAME
    journal = game / helper.JOURNAL_NAME
    target = game / "args.txt"
    original_fsync = helper._fsync_dir
    injected = False

    def fail_after_manifest_publication(path):
        nonlocal injected
        if not injected and manifest.exists() and target.exists():
            injected = True
            raise OSError("injected manifest durability failure")
        return original_fsync(path)

    monkeypatch.setattr(helper, "_fsync_dir", fail_after_manifest_publication)
    with pytest.raises(OSError):
        helper.install(game, [str(source), "args.txt"])
    assert manifest.exists()
    assert journal.exists()
    assert target.read_bytes() == b"installer"

    monkeypatch.setattr(helper, "_fsync_dir", original_fsync)
    helper.recover(game, journal)
    assert manifest.exists()
    assert target.read_bytes() == b"installer"
    assert not journal.exists()
    assert not any(game.glob(".args.txt.um-part-*"))


def test_release_verifier_rejects_duplicate_record_rows():
    verifier = _release_verifier_module()
    rows = [["um/__init__.py", "sha256=x", "1"], ["um/__init__.py", "sha256=x", "1"]]
    with pytest.raises(SystemExit):
        verifier.validate_record_rows(rows, {"um/__init__.py"})


def test_release_verifier_rejects_forbidden_sdist_directories():
    verifier = _release_verifier_module()
    with pytest.raises(SystemExit):
        verifier.validate_sdist_paths(["universal_modder-0.2.0/.venv/"])


def test_release_verifier_rejects_dirty_source_checkout(tmp_path):
    verifier = _release_verifier_module()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    (tmp_path / "tracked").write_text("clean", encoding="utf-8")
    subprocess.run(["git", "add", "tracked"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "clean"], cwd=tmp_path, check=True)
    (tmp_path / "tracked").write_text("dirty", encoding="utf-8")
    with pytest.raises(SystemExit):
        verifier.source_identity(tmp_path)


def test_release_verifier_reads_only_the_frozen_commit(tmp_path):
    verifier = _release_verifier_module()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    (tmp_path / "tracked").write_text("A", encoding="utf-8")
    subprocess.run(["git", "add", "tracked"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "A"], cwd=tmp_path, check=True)
    frozen = verifier.source_identity(tmp_path)["commit"]
    (tmp_path / "tracked").write_text("B", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "B"], cwd=tmp_path, check=True)
    assert verifier.git_blob(tmp_path, frozen, "tracked") == b"A"
    assert verifier.git_paths(tmp_path, frozen) == {"tracked"}


def test_release_identity_derives_tree_from_the_frozen_commit(tmp_path, monkeypatch):
    verifier = _release_verifier_module()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    (tmp_path / "tracked").write_text("A", encoding="utf-8")
    subprocess.run(["git", "add", "tracked"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "A"], cwd=tmp_path, check=True)
    commit_a = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    tree_a = subprocess.check_output(["git", "rev-parse", f"{commit_a}^{{tree}}"], cwd=tmp_path, text=True).strip()
    (tmp_path / "tracked").write_text("B", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "B"], cwd=tmp_path, check=True)
    commit_b = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    subprocess.run(["git", "checkout", "-q", commit_a], cwd=tmp_path, check=True)
    original = verifier.subprocess.check_output

    def move_head_before_tree(command, *args, **kwargs):
        if command[:2] == ["git", "rev-parse"] and command[-1].endswith("^{tree}"):
            subprocess.run(["git", "reset", "--hard", "-q", commit_b], cwd=tmp_path, check=True)
        return original(command, *args, **kwargs)

    monkeypatch.setattr(verifier.subprocess, "check_output", move_head_before_tree)
    identity = verifier.source_identity(tmp_path)
    assert identity == {"commit": commit_a, "tree": tree_a}


def test_release_identity_ignores_git_replacement_objects(tmp_path):
    verifier = _release_verifier_module()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    (tmp_path / "tracked").write_text("A", encoding="utf-8")
    subprocess.run(["git", "add", "tracked"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "A"], cwd=tmp_path, check=True)
    commit_a = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    tree_a = subprocess.check_output(["git", "--no-replace-objects", "rev-parse", f"{commit_a}^{{tree}}"], cwd=tmp_path, text=True).strip()
    (tmp_path / "tracked").write_text("B", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "B"], cwd=tmp_path, check=True)
    commit_b = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    subprocess.run(["git", "replace", commit_a, commit_b], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "-q", commit_a], cwd=tmp_path, check=True)
    subprocess.run(["git", "reset", "--hard", "-q", commit_a], cwd=tmp_path, check=True)
    with pytest.raises(SystemExit):
        verifier.source_identity(tmp_path)
    subprocess.run(["git", "--no-replace-objects", "reset", "--hard", "-q", commit_a], cwd=tmp_path, check=True)
    assert verifier.source_identity(tmp_path) == {"commit": commit_a, "tree": tree_a}


def test_release_verifier_rejects_symlink_distribution_input(tmp_path):
    verifier = _release_verifier_module()
    real = tmp_path / "real.whl"
    real.write_bytes(b"wheel")
    link = tmp_path / "linked.whl"
    link.symlink_to(real)
    with pytest.raises(SystemExit):
        verifier.snapshot_regular_file(link, tmp_path / "snapshot.whl")


def test_release_verifier_rejects_hardlinked_distribution_input(tmp_path):
    verifier = _release_verifier_module()
    source = tmp_path / "candidate.whl"
    source.write_bytes(b"wheel")
    os.link(source, tmp_path / "other-name.whl")
    with pytest.raises(SystemExit):
        verifier.snapshot_regular_file(source, tmp_path / "snapshot.whl")


def test_release_verifier_rejects_live_path_mutation_after_snapshot(tmp_path):
    verifier = _release_verifier_module()
    source = tmp_path / "candidate.whl"
    source.write_bytes(b"reviewed")
    binding = verifier.source_binding(source)
    source.write_bytes(b"mutated")
    with pytest.raises(SystemExit):
        verifier.verify_source_binding(source, binding)


def test_release_verifier_main_rechecks_named_inputs_before_success(tmp_path, monkeypatch):
    verifier = _release_verifier_module()
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    names = [f"{verifier.DIST}-{verifier.VERSION}-py3-none-any.whl",
             f"{verifier.DIST}-{verifier.VERSION}.tar.gz"]
    for directory in (left, right):
        for name in names:
            (directory / name).write_bytes(b"same")
    identity = {"commit": "a" * 40, "tree": "b" * 40}
    monkeypatch.setattr(verifier, "source_identity", lambda _root: identity)
    monkeypatch.setattr(verifier, "inspect_wheel", lambda *_args: {"member"})

    def inspect_sdist(*_args):
        (left / names[0]).write_bytes(b"mutated-after-snapshot")
        return {"member"}

    monkeypatch.setattr(verifier, "inspect_sdist", inspect_sdist)
    monkeypatch.setattr(sys, "argv", ["verify_release_candidate.py", str(left), str(right)])
    with pytest.raises(SystemExit, match="changed after snapshot"):
        verifier.main()


def test_release_verifier_preserves_preexisting_snapshot_destination(tmp_path):
    verifier = _release_verifier_module()
    source = tmp_path / "candidate.whl"
    source.write_bytes(b"reviewed")
    destination = tmp_path / "snapshot.whl"
    destination.write_bytes(b"caller-owned")
    with pytest.raises(FileExistsError):
        verifier.snapshot_regular_file(source, destination)
    assert destination.read_bytes() == b"caller-owned"


def test_release_verifier_rejects_path_substitution_after_descriptor_open(tmp_path, monkeypatch):
    verifier = _release_verifier_module()
    source = tmp_path / "candidate.whl"
    source.write_bytes(b"reviewed")
    replacement = tmp_path / "replacement.whl"
    replacement.write_bytes(b"substituted")
    original_open = verifier.os.open
    swapped = False

    def swap_after_open(path, flags, *args, **kwargs):
        nonlocal swapped
        fd = original_open(path, flags, *args, **kwargs)
        if not swapped and Path(path) == source:
            swapped = True
            replacement.replace(source)
        return fd

    monkeypatch.setattr(verifier.os, "open", swap_after_open)
    with pytest.raises(SystemExit):
        verifier.snapshot_regular_file(source, tmp_path / "snapshot.whl")
